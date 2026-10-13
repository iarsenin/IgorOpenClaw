"""Candidate tests, not a production release or acoustic acceptance certificate."""
import base64
import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock
import wave

spec = importlib.util.spec_from_file_location('reliable_test', pathlib.Path(__file__).resolve().parents[1] / 'scripts/shrink_reliable.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)

AUDIT = '[COVERAGE]\nENTIRE ATTACHED AUDIO REVIEWED\n[VERDICT]\nPASS\n[ISSUES]\nNONE\n[UNCERTAINTIES]\nNONE\n[HEARD_START]\nNo, not three point seven.\n[HEARD_END]\nThat is the point.'
ENDING_AUDIT='[COVERAGE]\nENTIRE ATTACHED AUDIO REVIEWED\n[UNCERTAINTIES]\nNONE\n[ENDING]\nThat is the point.'


def wav(path, seconds=3):
    with wave.open(str(path), 'wb') as out:
        out.setparams((1,2,r.base.RATE,0,'NONE','not compressed'))
        out.writeframes(bytes([1,0]) * (seconds * r.base.RATE))


class ReliableTests(unittest.TestCase):
    def test_audio_audit_accepts_crlf_without_dropping_any_issue_or_uncertainty(self):
        lf=AUDIT.replace('[ISSUES]\nNONE','[ISSUES]\nA clipped word.').replace('[UNCERTAINTIES]\nNONE','[UNCERTAINTIES]\nA number is uncertain.')
        self.assertEqual(r.base.parse_audio_text_report(lf),r.base.parse_audio_text_report(lf.replace('\n','\r\n')))
        with self.assertRaises(r.base.ShrinkError):r.base.require_pass(r.base.parse_audio_text_report(lf.replace('\n','\r\n')),[])
    def test_audio_provider_is_chosen_before_requests_and_does_not_retry_quality(self):
        with tempfile.TemporaryDirectory() as temp,mock.patch.object(r.base,'load_env'), \
             mock.patch.dict(r.base.os.environ,{'OPENAI_API_KEY':'fake','GOOGLE_API_KEY':'fake',
                'SHRINK_PROVIDER':'gemini'},clear=True):
            client=r.PairClient(pathlib.Path(temp))
            self.assertEqual(client.provider,'gemini');self.assertEqual(client.audio_provider,'openai')
            primary=mock.Mock();alternate=mock.Mock(return_value='actual audio path')
            self.assertEqual(client.audio_routed(pathlib.Path(temp),primary,alternate),'actual audio path')
            primary.assert_not_called();alternate.assert_called_once()
            alternate.side_effect=r.base.ShrinkError('Held quality report')
            with self.assertRaises(r.base.ShrinkError):client.audio_routed(pathlib.Path(temp),primary,alternate)
            primary.assert_not_called()
            with mock.patch.dict(r.base.os.environ,{'SHRINK_OPENAI_FALLBACK':'0'}):
                self.assertEqual(r.PairClient(pathlib.Path(temp)).audio_provider,'gemini')
                with mock.patch.dict(r.base.os.environ,{'SHRINK_AUDIO_PROVIDER':'openai'}):
                    self.assertEqual(r.PairClient(pathlib.Path(temp)).audio_provider,'openai')
    def test_ending_verifier_never_sends_previous_complaint_or_expected_words(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(r.base,'load_env'), \
             mock.patch.dict(r.base.os.environ,{'OPENAI_API_KEY':'fake-test','SHRINK_PROVIDER':'openai'},clear=True):
            root=pathlib.Path(temp);source=root/'source.wav';output=root/'output.wav';wav(source);wav(output)
            complaint={**r.base.parse_audio_text_report(AUDIT),'pass':False,'issues':['UNTRUSTED-PRIOR-CLAIM'],
                'heard_end':'UNTRUSTED-EXPECTED-PHRASE'}
            response=mock.Mock(ok=True,status_code=200,headers={})
            response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':ENDING_AUDIT}}]}
            client=r.PairClient(root)
            with mock.patch.object(r.base.requests,'request',return_value=response) as call:
                client.verify_boundary_claim(root/'review',source,output,complaint)
            bodies=[v.kwargs['json'] for v in call.call_args_list]
            self.assertEqual(len(bodies),2)
            sent=json.dumps([v['messages'] for v in bodies])
            self.assertNotIn('UNTRUSTED-PRIOR-CLAIM',sent);self.assertNotIn('UNTRUSTED-EXPECTED-PHRASE',sent)
            self.assertTrue(all(v['messages'][0]['content']==r.ENDING_SYSTEM for v in bodies))
            contract=r.base.read(root/'review/boundary-contract.json')
            self.assertEqual(contract['original_report'],complaint)
            self.assertFalse(contract['original_report_supplied_to_provider'])
            self.assertEqual(contract['protocol'],r.BOUNDARY_PROTOCOL)
            received=[base64.b64decode(x['input_audio']['data']) for body in bodies
                for x in body['messages'][1]['content'] if x['type']=='input_audio']
            self.assertEqual(received,[source.read_bytes(),output.read_bytes()])
            self.assertTrue(all(sum(x['type']=='input_audio' for x in body['messages'][1]['content'])==1 for body in bodies))

    def test_uncertain_first_reading_stops_peer_and_does_not_replay(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(r.base,'load_env'), \
             mock.patch.dict(r.base.os.environ,{'OPENAI_API_KEY':'fake-test','SHRINK_PROVIDER':'openai'},clear=True):
            root=pathlib.Path(temp);source=root/'source.wav';output=root/'output.wav';wav(source);wav(output)
            complaint={**r.base.parse_audio_text_report(AUDIT),'pass':False,'issues':['The output ends abruptly with missing speech.']}
            uncertain=ENDING_AUDIT.replace('[UNCERTAINTIES]\nNONE',
                '[UNCERTAINTIES]\nThe final sound is unclear.')
            response=mock.Mock(ok=True,status_code=200,headers={})
            response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':uncertain}}]}
            client=r.PairClient(root)
            with mock.patch.object(r.base.requests,'request',return_value=response) as call:
                for _ in range(2):
                    with self.assertRaises(r.base.ShrinkError):client.verify_boundary_claim(root/'review',source,output,complaint)
            self.assertEqual(call.call_count,1)
            self.assertFalse((root/'review/stages/ending-output/attempt.json').exists())

    def test_boundary_verification_never_waives_other_damage_or_uncertainty(self):
        context={'source_eof':True,'output_eof':True,'uncut_source_tail':True}
        original={**r.base.parse_audio_text_report(AUDIT),'pass':False,
            'issues':['The output ends abruptly, omitting the remainder of the sentence.']}
        reading={'complete':True,'uncertainties':[],'heard_end':'and then if you build'}
        verification={'source':reading,'output':{**reading,'heard_end':'And then if you build.'}}
        r.require_boundary_resolution(original,verification,context)
        for field in context:
            self.assertFalse(r.boundary_claim_eligible(original,{**context,field:False}))
        for issue in ['The final negative is missing.', 'The ending has new noise.',
                      'The final speaker has changed.', 'A repeated word and missing sentence ending.']:
            self.assertFalse(r.boundary_claim_eligible({**original,'issues':[issue]},context))
        for failed in ({**reading,'heard_end':'and then you build'},
                       {**reading,'heard_end':'yes'},
                       {**reading,'uncertainties':['The final word is unclear.']},
                       {**reading,'complete':False},
                       {**reading,'issues':['Unexpected field cannot be silently dropped.']}):
            for label in ('source','output'):
                with self.assertRaises(r.base.ShrinkError):r.require_boundary_resolution(original,{**verification,label:failed},context)

    def test_literal_reading_parser_keeps_uncertainty_and_rejects_extra_or_incomplete_fields(self):
        expected={'complete':True,'uncertainties':[],'heard_end':'That is the point.'}
        self.assertEqual(r.parse_ending_report(ENDING_AUDIT),expected)
        self.assertEqual(r.parse_ending_report(json.dumps({'COVERAGE':'ENTIRE ATTACHED AUDIO REVIEWED',
            'UNCERTAINTIES':'NONE','ENDING':'That is the point.'})),expected)
        for text in (ENDING_AUDIT.replace('ENTIRE ATTACHED AUDIO REVIEWED','INCOMPLETE'),
                     ENDING_AUDIT.replace('[UNCERTAINTIES]\nNONE','[UNCERTAINTIES]\nA final word is unclear.')):
            with self.assertRaises(r.base.ShrinkError):r.require_ending_reading(r.parse_ending_report(text))
        for text in ('A guessed ending',ENDING_AUDIT.replace('[ENDING]','[UNKNOWN]'),
                     ENDING_AUDIT+'\n[EXTRA]\nUnexpected content.',
                     '{"COVERAGE":"ENTIRE ATTACHED AUDIO REVIEWED","UNCERTAINTIES":"NONE","ENDING":"one","ENDING":"two"}'):
            with self.assertRaises(r.base.ShrinkError):r.parse_ending_report(text)

    def test_partition_rejects_gap_overlap_reorder_missing_tail_and_oversize(self):
        r.validate_partition([[0,10],[10,20]],20,10)
        for values in ([[0,9],[10,20]], [[0,11],[10,20]], [[10,20],[0,10]], [[0,10]], [[0,20]], []):
            with self.subTest(values=values), self.assertRaises(r.base.ShrinkError):r.validate_partition(values,20,10)

    def test_physical_extract_preserves_all_selected_samples_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp); source=root/'input.wav'; output=root/'extract.wav'; wav(source)
            receipt=r.extract_pcm(source,output,123,10003)
            with wave.open(str(source),'rb') as a, wave.open(str(output),'rb') as b:
                a.setpos(123); self.assertEqual(a.readframes(9880),b.readframes(9880))
            self.assertFalse(receipt['lexical_or_onset_evidence'])
            with self.assertRaises(r.base.ShrinkError):r.extract_pcm(source,output,123,10003)

    def test_quiet_partition_owns_every_frame_without_deleting_or_reordering(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp)/'source.wav'; wav(p,7)
            ranges=r.partition_pcm(p,3)
            self.assertEqual(ranges[0][0],0);self.assertEqual(ranges[-1][-1],7*r.base.RATE)
            self.assertEqual(sum(b-a for a,b in ranges),7*r.base.RATE)
            self.assertTrue(all(a[1]==b[0] for a,b in zip(ranges,ranges[1:])))

    @unittest.skipUnless(shutil.which('ffmpeg'),'FFmpeg needed')
    def test_real_encode_decode_preserves_complete_delivery_frame_ownership(self):
        with tempfile.TemporaryDirectory() as temp:
            root=pathlib.Path(temp); p=root/'source.wav'; wav(p,7)
            parts=r.encode_parts(p,root/'parts',r.partition_pcm(p,3))
            self.assertEqual(sum(p['last_frame']-p['first_frame'] for p in parts),7*r.base.RATE)
            self.assertTrue(all(r.base.pcm_info(pathlib.Path(p['listening']))['frames']==p['last_frame']-p['first_frame'] for p in parts))

    def test_comparison_sends_both_exact_inputs_text_only_raw_before_parse(self):
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(r.base,'load_env'), mock.patch.dict(r.base.os.environ,{'OPENAI_API_KEY':'fake-test','SHRINK_PROVIDER':'openai'},clear=True):
            root=pathlib.Path(temp); source=root/'source.wav'; output=root/'output.wav'; wav(source); wav(output)
            response=mock.Mock(ok=True,status_code=200,headers={});response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':AUDIT}}]}
            client=r.PairClient(root)
            with mock.patch.object(r.base.requests,'request',return_value=response) as call:
                result=client.compare(root/'review',source,output,{'tempo':1,'removed_intervals':[]})
            r.base.require_pass(result,[])
            body=call.call_args.kwargs['json'];self.assertEqual(body['modalities'],['text']);self.assertNotIn('audio',body);self.assertNotIn('tools',body)
            received=[base64.b64decode(x['input_audio']['data']) for x in body['messages'][1]['content'] if x['type']=='input_audio']
            self.assertEqual(received,[source.read_bytes(),output.read_bytes()])
            self.assertEqual(r.base.read(root/'review/openai/raw.json'),response.json.return_value)
            with self.assertRaises(r.base.ShrinkError), mock.patch.object(r.base.requests,'request',side_effect=AssertionError('No replay')):
                client.compare(root/'review',source,output,{'tempo':1,'removed_intervals':[]})

    def test_reference_condition_is_not_instruction_to_ignore_new_defects(self):
        prompt=r.pair_prompt({'seconds':3},{'seconds':3},{'tempo':1})
        self.assertIn('every voice and meaningful phrase',prompt)
        self.assertIn('missing/repeated speech',prompt)
        self.assertIn('uncertainty',prompt)
        self.assertNotIn('expected words',prompt)


if __name__=='__main__':unittest.main()
