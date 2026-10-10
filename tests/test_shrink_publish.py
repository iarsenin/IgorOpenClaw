import importlib.util
import json
import pathlib
import unittest

spec=importlib.util.spec_from_file_location('publish_test',pathlib.Path(__file__).resolve().parents[1]/'scripts/shrink_publish.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
PASS={'pass':True,'issues':[],'uncertainties':[],'checked_ids':[],'protected_ids':[],
    'heard_start':'actual phrase','heard_end':'actual ending'}


class PublishTests(unittest.TestCase):
    def test_review_windows_must_cover_every_sample_without_gaps(self):
        windows=[{'first_frame':0,'last_frame':240000,'report':PASS},{'first_frame':192000,'last_frame':400000,'report':PASS}]
        s.validate_windows(windows,400000)
        for changed in ([windows[0]], [{**windows[0],'first_frame':1},windows[1]],
            [windows[0],{**windows[1],'first_frame':250000}], [windows[0],{**windows[1],'report':{**PASS,'issues':['Clipped negative.']}}]):
            with self.assertRaises(s.b.ShrinkError):s.validate_windows(changed,400000)

    def test_real_cli_receipt_requires_correct_channel_target_message_id_and_not_dry_run(self):
        value={'action':'send','channel':'whatsapp','dryRun':False,'messageId':'3EB-real-message','payload':{'to':'+15551234567','result':{'messageId':'3EB-real-message'}}}
        text='harmless progress\n'+json.dumps(value)
        self.assertEqual(s.parse_send_receipt(text,'+15551234567'),value)
        for bad in ({**value,'dryRun':True},{**value,'channel':'telegram'},{**value,'messageId':''},
            {**value,'payload':{'to':'+15557654321'}},{**value,'payload':{'to':'+15551234567','deliveryStatus':'queued'}}):
            with self.assertRaises(s.b.ShrinkError):s.parse_send_receipt(json.dumps(bad),'+15551234567')
        with self.assertRaises(s.b.ShrinkError):s.parse_send_receipt('not a platform receipt','+15551234567')
        with self.assertRaises(s.b.ShrinkError):s.parse_send_receipt(json.dumps(value)+'\n'+json.dumps(value),'+15551234567')


if __name__=='__main__':unittest.main()
