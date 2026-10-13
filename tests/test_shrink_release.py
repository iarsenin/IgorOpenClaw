"""Release mechanics: synthetic fixtures/mock reports are NOT listening approval."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import wave

spec=importlib.util.spec_from_file_location('release_publish',Path(__file__).resolve().parents[1]/'scripts/shrink_publish.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
p,b=s.p,s.b
PASS={'pass':True,'issues':[],'uncertainties':[],'checked_ids':[],'protected_ids':[],
      'heard_start':'unit fixture opening','heard_end':'unit fixture ending'}


def response(root,report,audio):
    private=root/'openai';private.mkdir(parents=True,exist_ok=True)
    if audio:
        fields={'COVERAGE':'ENTIRE ATTACHED AUDIO REVIEWED','VERDICT':'PASS' if report['pass'] else 'FAIL',
                'ISSUES':'\n'.join(report['issues']) or 'NONE',
                'UNCERTAINTIES':'\n'.join(report['uncertainties']) or 'NONE',
                'HEARD_START':report['heard_start'],'HEARD_END':report['heard_end']}
        raw={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(fields)}}]}
    else:
        raw={'status':'completed','output':[{'type':'message','role':'assistant','status':'completed',
             'content':[{'type':'output_text','text':json.dumps(report)}]}]}
    b.save(private/'raw.json',raw)
    b.save(private/'request-attempt.json',{'status':'received','http_status':200,'raw_sha256':b.sha(private/'raw.json')})
    return report


class FakeClient:
    provider_config={};provider='openai';quota_stop=False;openai_text='fake';edit='fake'
    def __init__(self,directory):pass
    def generate(self,root,*args):
        return {'cuts':[],'pauses':[],'protected':[{'id':'P1','first_word':0,'last_word':2,'reason':'Keep all words'}],'notes':[]}
    def independent_text_review(self,root,prompt):
        return response(root,{k:v for k,v in {**PASS,'protected_ids':['P1']}.items() if not k.startswith('heard_')},False)
    def compare(self,root,source,output,transform):
        b.save(root/'comparison-contract.json',{'source_info':b.pcm_info(source),'output_info':b.pcm_info(output)})
        return response(root,PASS,True)
    def review_uncut_output(self,root,audio):
        b.save(root/'uncut-quality-contract.json',{'profile':'uncut-source-preservation','input':b.pcm_info(audio),'prompt':'unit mechanics'})
        return response(root,PASS,True)


class FakeBoundaryClient(FakeClient,p.r.PairClient):
    def compare(self,root,source,output,transform):
        b.save(root/'comparison-contract.json',{'source_info':b.pcm_info(source),'output_info':b.pcm_info(output)})
        return response(root,{**PASS,'pass':False,'issues':['The output ends abruptly, missing the remainder of the sentence.']},True)
    def read_ending(self,root,audio,prompt):
        b.save(root/'ending-reading-contract.json',{'protocol':p.r.BOUNDARY_PROTOCOL,'input':b.pcm_info(audio),
            'system':p.r.ENDING_SYSTEM,'prompt':prompt,'schema':p.r.ENDING_SCHEMA})
        private=root/'openai'
        fields={'COVERAGE':'ENTIRE ATTACHED AUDIO REVIEWED','UNCERTAINTIES':'NONE','ENDING':'unit fixture ending'}
        b.save(private/'raw.json',{'choices':[{'finish_reason':'stop','message':{'content':json.dumps(fields)}}]})
        b.save(private/'request-attempt.json',{'status':'received','http_status':200,'raw_sha256':b.sha(private/'raw.json')})
        return p.r.parse_ending_report(json.dumps(fields))


class DisputedEditClient(FakeClient):
    reject_at='text'
    def generate(self,root,*args):
        return {'cuts':[{'first_word':1,'last_word':1,'reason':'A deliberately unsafe proposal for the test'}],
            'pauses':[],'protected':[{'id':'P1','first_word':0,'last_word':0,'reason':'Opening'},
                {'id':'P2','first_word':2,'last_word':2,'reason':'Quantity'}],'notes':[]}
    def independent_text_review(self,root,prompt):
        conservative=root.name=='text-review-conservative'
        report={'pass':conservative or self.reject_at!='text','issues':[] if conservative or self.reject_at!='text'
            else ['Proposed cut removes a negative.'],'uncertainties':[],
            'checked_ids':[] if conservative else [0],'protected_ids':['all-original-words'] if conservative else ['P1','P2']}
        return response(root,report,False)
    def review_edit(self,root,source,output,proposal):
        b.save(root/'edit-comparison-contract.json',{'source':b.pcm_info(source),'output':b.pcm_info(output),'proposal':proposal})
        return response(root,{**PASS,'pass':False,'issues':['A proposed join clips speech.']},True)


class DisputedJoinClient(DisputedEditClient):
    reject_at='join'


class BoundaryEditedClient(DisputedEditClient,FakeBoundaryClient):
    reject_at='none'
    def review_edit(self,root,source,output,proposal):
        b.save(root/'edit-comparison-contract.json',{'source':b.pcm_info(source),'output':b.pcm_info(output),'proposal':proposal})
        return response(root,PASS,True)


class ReleaseTests(unittest.TestCase):
    def build(self,root,client=FakeClient,seconds=16):
        source=root/'source.wav'
        with wave.open(str(source),'wb') as stream:
            stream.setparams((1,2,b.RATE,0,'NONE','not compressed'));stream.writeframes(bytes([1,0])*seconds*b.RATE)
        original={'url':'https://example.com/unit','title':'unit mechanical fixture','master':b.pcm_info(source)}
        words=[{'id':i,'text':word,'start':1+i,'end':1.5+i,'segment':0,'speaker_local':None}
               for i,word in enumerate(['No','not','three'])]
        directory=root/'job';directory.mkdir();b.save(directory/'input.json',original)
        args=argparse.Namespace(url=original['url'],output=str(directory),tempo=1.08)
        with mock.patch.object(p,'source_for_job',return_value=(source,original,words,[source])), \
             mock.patch.object(p,'sentence_boundary_hints',return_value=[]):
            result=p.run_job(args,client)
        b.save(directory/'job.json',{'policy':p.POLICY,'target':'+15551234567','status':'running',
               'code_fingerprint':b.release_fingerprint()})
        return directory,result

    def test_complete_pipeline_preflight_then_once_only_real_receipt_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);directory,result=self.build(root)
            _,proof=s.preflight(directory)
            self.assertEqual(proof['complete_parts'],1);self.assertEqual(proof['complete_windows'],1)
            s.authorize_automatic_delivery(directory,'+15551234567')
            receipt={'action':'send','channel':'whatsapp','dryRun':False,'messageId':'unit-message',
                     'payload':{'to':'+15551234567'}}
            real_run=s.subprocess.run
            def subprocess_run(command,*args,**kwargs):
                if command[0]=='fake-cli':return mock.Mock(returncode=0,stdout=json.dumps(receipt),stderr='')
                return real_run(command,*args,**kwargs)
            with mock.patch.object(s.shutil,'which',return_value='fake-cli'),mock.patch.object(s.Path,'home',return_value=root), \
                 mock.patch.object(s.subprocess,'run',side_effect=subprocess_run) as calls:
                s.deliver(directory,'+15551234567');s.deliver(directory,'+15551234567')
                self.assertEqual(sum(call.args[0][0]=='fake-cli' for call in calls.call_args_list),1)
            self.assertFalse((directory/'main-final-acceptance.json').exists())

    def test_disputed_text_or_join_keeps_all_original_speech_with_fresh_full_checks(self):
        for client in (DisputedEditClient,DisputedJoinClient):
            with self.subTest(stage=client.reject_at),tempfile.TemporaryDirectory() as temp:
                directory,result=self.build(Path(temp),client)
                self.assertEqual(result['cut_count'],0)
                self.assertEqual(b.read(directory/'edit-plan.json')['retained_intervals'],[[0,16]])
                self.assertTrue((directory/'edit-plan-before-recovery.json').exists())
                self.assertTrue((directory/'conservative-edit-recovery.json').exists())
                self.assertIn('text-review-conservative',result['text_evidence']['stage'])
                s.preflight(directory)
                with self.assertRaises(b.ShrinkError):
                    p.retain_original_after_edit_rejection(directory,client(directory),{},None,{},[], 'No second recovery',{})

    def test_raw_tampering_missing_tail_and_cross_input_reports_fail_before_send(self):
        with tempfile.TemporaryDirectory() as temp:
            directory,result=self.build(Path(temp));original=copy.deepcopy(result)
            for change in ('tail','scope','raw','text'):
                changed=copy.deepcopy(original);part=changed['chat_audio'][0]
                if change=='tail':part['last_frame']-=1
                if change=='scope':part['extraction']['first_frame']+=1
                if change=='raw':part['quality_evidence']['files'].pop('openai/raw.json')
                if change=='text':changed['text_report']['protected_ids']=[]
                b.save(directory/'result.json',changed)
                with self.subTest(change=change),self.assertRaises(b.ShrinkError):s.preflight(directory)

    def test_automatic_acceptance_cannot_transfer_to_wrong_recipient_or_historical_case(self):
        with tempfile.TemporaryDirectory() as temp:
            directory,result=self.build(Path(temp))
            with self.assertRaises(b.ShrinkError):s.authorize_automatic_delivery(directory,'+15557654321')
            result['policy']='source-relative-candidate-v2';b.save(directory/'result.json',result)
            with self.assertRaises(b.ShrinkError):s.authorize_automatic_delivery(directory,'+15551234567')

    def test_ambiguous_delivery_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as temp:
            directory,result=self.build(Path(temp));s.authorize_automatic_delivery(directory,'+15551234567')
            b.save(directory/'delivery-000.json',{'status':'sending','fingerprint':'uncertain'})
            with mock.patch.object(s.shutil,'which',return_value='fake-cli'),mock.patch.object(s.Path,'home',return_value=Path(temp)),self.assertRaises(b.ShrinkError):
                s.deliver(directory,'+15551234567')

    def test_ending_resolution_rechecks_two_actual_raw_readings_and_preserves_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            directory,result=self.build(Path(temp),BoundaryEditedClient,seconds=30)
            entry=result['chat_audio'][0]['comparison_reports'][0]
            self.assertFalse(entry['report']['pass'])
            self.assertEqual(set(entry['boundary_resolution']['report']),{'source','output'})
            s.preflight(directory)
            changed=copy.deepcopy(result)
            changed['chat_audio'][0]['comparison_reports'][0]['boundary_resolution']['reading_evidence']['output']=entry['boundary_resolution']['reading_evidence']['source']
            b.save(directory/'result.json',changed)
            with self.assertRaises(b.ShrinkError):s.preflight(directory)

    def test_uncut_profile_never_waives_a_real_cut_or_output_uncertainty(self):
        with tempfile.TemporaryDirectory() as temp:
            directory,result=self.build(Path(temp),BoundaryEditedClient,seconds=30)
            result['verification_profile']='uncut-source-preservation';b.save(directory/'result.json',result)
            with self.assertRaises(b.ShrinkError):s.preflight(directory)
        with tempfile.TemporaryDirectory() as temp:
            directory,result=self.build(Path(temp))
            result['chat_audio'][0]['review']['uncertainties']=['The outgoing sound is garbled.']
            b.save(directory/'result.json',result)
            with self.assertRaises(b.ShrinkError):s.preflight(directory)


if __name__=='__main__':unittest.main()
