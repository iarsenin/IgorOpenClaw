import argparse
import importlib.util
import json
import pathlib
import tempfile
import unittest
from unittest import mock
import wave

spec=importlib.util.spec_from_file_location('pipeline_test',pathlib.Path(__file__).resolve().parents[1]/'scripts/shrink_pipeline.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def words():return [{'id':i,'text':t,'speaker_local':None,'segment':0,'start':i+1,'end':i+1.3}
    for i,t in enumerate(['not','three','point','seven','it','took','it','took','a','while'])]


def audio(path,seconds=16):
    with wave.open(str(path),'wb') as out:
        out.setparams((1,2,p.b.RATE,0,'NONE','not compressed'));out.writeframes(b'\x01\0'*(seconds*p.b.RATE))


PASS={'pass':True,'issues':[],'uncertainties':[],'checked_ids':[],'protected_ids':[],
    'heard_start':'unit-test-only boundary','heard_end':'unit-test-only ending'}


class PipelineTests(unittest.TestCase):
    def test_failed_boundary_verification_is_preserved_and_never_replayed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);source=root/'source.wav';audio(source)
            failed={**PASS,'pass':False,'issues':['The output ends abruptly, omitting the remainder of the sentence.']}
            client=mock.Mock();client.verify_boundary_claim.return_value=failed
            context={'source_eof':True,'output_eof':True,'uncut_source_tail':True}
            for _ in range(2):
                with self.assertRaises(p.b.ShrinkError):p.review_decision(root,client,failed,source,source,context)
            client.verify_boundary_claim.assert_called_once()
            self.assertEqual(p.b.read(root/'stages/boundary-claim-verification/result.json'),failed)
            self.assertEqual(failed['pass'],False)

    def test_budget_counts_failures_and_blocks_before_next_request(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(p.b,'load_env'), \
             mock.patch.dict(p.b.os.environ,{'SHRINK_PROVIDER':'openai','OPENAI_API_KEY':'fake-unit'},clear=True):
            client=p.EditClient(pathlib.Path(temp));client.request_limit=1
            client.reserve_request('openai','test')
            with self.assertRaises(p.b.ShrinkError):client.reserve_request('openai','test')
            self.assertEqual(p.b.read(client.budget_path)['requests_started'],1)

    def test_boundary_context_is_derived_from_final_physical_frames_and_cut_history(self):
        safe=p.boundary_context(100*p.b.RATE,95*p.b.RATE,100*p.b.RATE,95*p.b.RATE,[])
        self.assertTrue(all(safe.values()))
        self.assertFalse(p.boundary_context(100*p.b.RATE,95*p.b.RATE,99*p.b.RATE,95*p.b.RATE,[])['source_eof'])
        self.assertFalse(p.boundary_context(100*p.b.RATE,95*p.b.RATE,100*p.b.RATE,95*p.b.RATE,[{'end':99}])['uncut_source_tail'])

    def test_semantic_view_preserves_exact_word_id_speaker_and_segment(self):
        value=p.semantic_navigation(words());back=[]
        for group in value['groups']:
            for i,text in enumerate(group['words']):back.append((group['first_id']+i,text,group['speaker_local'],group['segment']))
        self.assertEqual(back,[(w['id'],w['text'],w['speaker_local'],w['segment']) for w in words()])
        with self.assertRaises(p.b.ShrinkError):p.semantic_navigation(words()[1:])
        retained=[w for w in words() if w['id'] not in {4,5}]
        packed=p.semantic_navigation(retained,complete=False);back=[]
        for group in packed['groups']:
            for i,text in enumerate(group['words']):back.append((group['first_id']+i,text))
        self.assertEqual(back,[(w['id'],w['text']) for w in retained])

    def test_independent_critic_uses_reasoning_responses_with_strict_schema(self):
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(p.b,'load_env'),mock.patch.dict(p.b.os.environ,{'OPENAI_API_KEY':'fake','SHRINK_PROVIDER':'openai'},clear=True):
            root=pathlib.Path(temp);client=p.EditClient(root)
            report={'pass':True,'issues':[],'uncertainties':[],'checked_ids':[0],'protected_ids':['P1']}
            payload={'status':'completed','output':[{'type':'reasoning'},{'type':'message','role':'assistant','status':'completed',
                'content':[{'type':'output_text','text':json.dumps(report)}]}]}
            response=mock.Mock(ok=True,status_code=200,headers={});response.json.return_value=payload
            with mock.patch.object(p.b.requests,'request',return_value=response) as call:
                self.assertEqual(client.independent_text_review(root/'review','source and retained'),report)
            body=call.call_args.kwargs['json'];self.assertEqual(body['model'],'gpt-6-sol');self.assertEqual(body['reasoning'],{'effort':'low'})
            self.assertTrue(body['text']['format']['strict']);self.assertNotIn('temperature',body);self.assertNotIn('tools',body)
            self.assertEqual(p.b.read(root/'review/openai/raw.json'),payload)

    def test_repeat_cues_are_explicitly_provisional_never_deletions(self):
        cues=p.repeated_phrase_cues(words())
        self.assertEqual(cues[0]['exact_first_text'],['it','took'])
        self.assertEqual(cues[0]['exact_surviving_text'],['it','took'])
        self.assertIn('emphasis',cues[0]['caution'])
        before=json.dumps(words());p.repeated_phrase_cues(words());self.assertEqual(before,json.dumps(words()))

    def test_physical_mapping_is_chronological_not_word_onset_proof(self):
        model=p.physical_model([[0,10],[12,20]])
        self.assertEqual(model[1]['cut_first'],round((10-p.b.FADE)*p.b.RATE))
        a,z=p.source_range_for_output(model,0,3*p.b.RATE,1.08,20*p.b.RATE)
        self.assertEqual(a,0);self.assertGreater(z,3*p.b.RATE)
        with self.assertRaises(p.b.ShrinkError):p.source_range_for_output(model,100*p.b.RATE,105*p.b.RATE,1.08,20*p.b.RATE)
        a,z=p.source_range_for_output(p.physical_model([[0,20]]),5*p.b.RATE,10*p.b.RATE,1.08,20*p.b.RATE)
        self.assertEqual(a,int(5.4*p.b.RATE))
        # Nominal atempo mapping is navigation, not word-onset evidence; an IEEE
        # ceil may conservatively own one additional source sample.
        self.assertLessEqual(abs(z-int(10.8*p.b.RATE)),1)

    def test_invalid_tempo_or_url_never_instantiates_a_paid_client(self):
        for url,tempo in [('file:///tmp/local',1.08),('https://example.com',float('nan')),('https://example.com',2)]:
            client=mock.Mock()
            with self.assertRaises(p.b.ShrinkError):p.run_job(argparse.Namespace(url=url,tempo=tempo),client)
            client.assert_not_called()

    def test_source_cache_must_match_exact_url_and_full_physical_master(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);p.b.save(root/'input.json',{'url':'https://example.com/a','master':{}})
            with self.assertRaises(p.b.ShrinkError):p.read_source_cache(root,'https://example.com/b')

    def test_geometry_veto_keeps_unsafe_speech_without_mutating_model_plan(self):
        nav=words();nav[3]['end']=nav[4]['start']
        plan={'cuts':[{'first_word':4,'last_word':5,'reason':'provisional false start'}], 'pauses':[],
            'protected':[{'first_word':0,'last_word':3,'reason':'Negative/quantity preserved','id':'P1'}],'notes':[]}
        before=json.dumps(plan);kept,vetoes=p.geometry_vetoes(plan,nav,12)
        self.assertEqual(kept['cuts'],[]);self.assertEqual(len(vetoes),1);self.assertEqual(json.dumps(plan),before)
        plan['cuts'][0]['first_word']=-1
        with self.assertRaises(p.b.ShrinkError):p.geometry_vetoes(plan,nav,12)

    def test_cache_reuses_exact_successful_raw_and_rejects_tampering_without_a_provider(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(p.b.requests,'request',side_effect=AssertionError('No API')):
            root=pathlib.Path(temp);source=root/'original.wav';audio(source)
            clip=root/'source-000.wav';p.r.extract_pcm(source,clip,0,16*p.b.RATE)
            original={'url':'https://example.com/cache','master':p.b.pcm_info(source),'title':'offline mechanics'}
            p.b.save(root/'input.json',original);stage=root/'stages/asr-000'
            raw={'language':'english','text':'No, not three.','duration':16,'words':[{'word':'No,','start':1,'end':1.4},
                {'word':'not','start':1.5,'end':1.9},{'word':'three.','start':2,'end':2.5}]}
            p.b.save(stage/'openai/raw.json',raw);result=p.b.parse_openai_transcript(raw)
            p.b.save(stage/'result.json',result)
            p.b.save(stage/'attempt.json',{'status':'complete','result_sha256':p.b.sha(stage/'result.json'),
                'binding':{'input':original,'clip':p.b.sha(clip),'provider_config':{'language':'en'}}})
            p.b.save(stage/'openai/request-attempt.json',{'status':'received','http_status':200,'model':'whisper-1','raw_sha256':p.b.sha(stage/'openai/raw.json')})
            _,_,nav,_,proof=p.read_source_cache(root,original['url'])
            self.assertEqual([w['text'] for w in nav],['No,','not','three.']);self.assertFalse(proof['source_or_editorial_acceptance_inherited'])
            p.b.save(stage/'result.json',{'text':'No, three.','words':result['words'][::2]})
            with self.assertRaises(p.b.ShrinkError):p.read_source_cache(root,original['url'])

    def test_semantic_rejection_of_provisional_restart_keeps_the_entire_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);source=root/'source.wav';audio(source)
            model=mock.Mock();model.review_edit.return_value={**PASS,'pass':False,'issues':['Different physical speakers.']}
            plan={'cuts':[],'pauses':[],'protected':[{'first_word':0,'last_word':9,'id':'P1','reason':'Meaning retained'}],'notes':[]}
            before=json.dumps(plan)
            result=p.acoustic_restarts(root,source,words(),model,{},plan)
            self.assertIsNone(result);self.assertEqual(json.dumps(plan),before);self.assertEqual(model.review_edit.call_count,1)
            decisions=p.b.read(root/'restart-decisions.json')['decisions']
            self.assertEqual(decisions[0]['disposition'],'retain');self.assertEqual(decisions[0]['complete_report']['issues'],['Different physical speakers.'])

    def test_validated_restart_still_needs_independent_complete_text_and_final_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);source=root/'source.wav';audio(source)
            model=mock.Mock();model.review_edit.return_value=PASS
            plan={'cuts':[],'pauses':[],'protected':[{'first_word':0,'last_word':9,'id':'P1','reason':'Meaning retained'}],'notes':[]}
            new,cuts,intervals,removed=p.acoustic_restarts(root,source,words(),model,{},plan)
            self.assertEqual(removed,{4,5});self.assertEqual(len(cuts),1);self.assertEqual(intervals[0][0],0);self.assertEqual(intervals[-1][1],16)
            self.assertEqual(plan['cuts'],[]);self.assertIn('independent',new['notes'][0].lower())
            protected=set().union(*(set(range(v['first_word'],v['last_word']+1)) for v in new['protected']))
            self.assertEqual(protected,set(range(10))-{4,5})

    def test_provider_failure_does_not_become_a_candidate_veto_or_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp);source=root/'source.wav';audio(source)
            model=mock.Mock();model.review_edit.side_effect=p.b.ShrinkError('HTTP429 - stop all')
            plan={'cuts':[],'pauses':[],'protected':[{'first_word':0,'last_word':9,'id':'P1','reason':'Meaning retained'}],'notes':[]}
            for _ in range(2):
                with self.assertRaises(p.b.ShrinkError):p.acoustic_restarts(root,source,words(),model,{},plan)
            self.assertEqual(model.review_edit.call_count,1);self.assertFalse((root/'restart-decisions.json').exists())


if __name__=='__main__':unittest.main()
