#!/usr/bin/env python3
"""Private reviewed-audio delivery with complete preflight and real CLI receipt checks."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

SPEC=importlib.util.spec_from_file_location('publish_delivery',Path(__file__).with_name('shrink_delivery.py'))
d=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(d);p,r,b=d.p,d.r,d.b


def validate_windows(entries,frames):
    if not entries:raise b.ShrinkError('No complete actual audio review windows.')
    previous=0
    for index,entry in enumerate(entries):
        first,last=entry['first_frame'],entry['last_frame']
        if type(first) is not int or type(last) is not int or not 0<=first<last<=frames:
            raise b.ShrinkError('Invalid actual review window.')
        if (index==0 and first!=0) or (index and first!=previous-2*b.RATE):
            raise b.ShrinkError('Audio review windows have a gap, reorder or unexpected overlap.')
        b.require_pass(entry['report'],[]);previous=last
    if previous!=frames:raise b.ShrinkError('Final actual audio samples were not all reviewed.')


def preflight(directory):
    directory=Path(directory).resolve();result=b.read(directory/'result.json')
    if result.get('policy')!='source-relative-delivery-repair-v1' or not result.get('source_relative_reviews'):
        raise b.ShrinkError('Only the fully reviewed current delivery case is supported by this publisher.')
    parent=Path(result['source_parent']);source=Path(b.read(parent/'source-reuse.json')['source']);original=b.read(directory/'input.json')
    if b.pcm_info(source)!=original['master'] or b.sha(result['audio'])!=result['audio_sha256']:
        raise b.ShrinkError('Original or final audio changed after review.')
    final=Path(result['audio']).parent/'edited.wav'
    if b.sha(final)!=result['rendered_wav_sha256']:raise b.ShrinkError('Final PCM changed after review.')
    edit=b.read(directory/'edit-plan.json');p.verify_retained_cut(source,final.parent/'cut.wav',edit['retained_intervals'])
    parts=result['chat_audio'];r.validate_partition([[v['first_frame'],v['last_frame']] for v in parts],b.pcm_info(final)['frames'],600*b.RATE)
    payloads=[]
    for index,part in enumerate(parts):
        audio,listen=Path(part['path']),Path(part['listening'])
        if b.sha(audio)!=part['sha256'] or b.sha(listen)!=part['listening_sha256'] or audio.stat().st_size>14*1024*1024:
            raise b.ShrinkError('Actual outgoing media changed or is oversized.')
        # Decode the exact file again, not a synthetic pass flag or another take.
        with tempfile.TemporaryDirectory(prefix='shrink-send-preflight-') as temp:
            decoded=Path(temp)/'actual.wav'
            b.command(['ffmpeg','-v','error','-n','-i',audio,'-ar',b.RATE,'-ac','1','-c:a','pcm_s16le',decoded])
            if b.pcm_info(decoded)!=b.pcm_info(listen):raise b.ShrinkError('Actual outgoing encode no longer decodes to the listened media.')
        validate_windows(part['comparison_reports'],part['last_frame']-part['first_frame'])
        for window,entry in enumerate(part['comparison_reports']):
            src,out=Path(entry['source']),Path(entry['output'])
            if b.pcm_info(src)!=entry['source_info'] or b.pcm_info(out)!=entry['output_info']:
                raise b.ShrinkError('A complete reviewed physical input changed.')
            p.prove_source_clip(listen,out,entry['first_frame'],entry['last_frame']-entry['first_frame'])
            scope=directory/'comparison-inputs'/f'{index:03d}-{window:03d}'
            if entry['reused']:
                proof=b.read(scope/'exact-comparison-reuse.json');stage=Path(proof['parent_stage'])
                if proof.get('actual_source_and_output_bytes_identical') is not True:raise b.ShrinkError('An inherited sound input is not byte-identical.')
            else:stage=directory/'stages'/f'final-compare-{index:03d}-{window:03d}'
            attempt=b.read(stage/'attempt.json');http=b.read(stage/'openai/request-attempt.json');raw=stage/'openai/raw.json';payload=b.read(raw)
            if (attempt.get('status')!='complete' or attempt.get('result_sha256')!=b.sha(stage/'result.json')
                or http.get('status')!='received' or http.get('http_status')!=200 or http.get('raw_sha256')!=b.sha(raw)
                or b.read(stage/'result.json')!=entry['report']):
                raise b.ShrinkError('Complete acoustic payload/receipt is missing or changed.')
            contract=b.read(stage/'comparison-contract.json')
            if contract['source_info']!=entry['source_info'] or contract['output_info']!=entry['output_info']:
                raise b.ShrinkError('Acoustic approval belongs to other actual inputs.')
            choices=payload.get('choices',[])
            if len(choices)!=1 or choices[0].get('finish_reason')!='stop' or b.parse_audio_text_report(choices[0]['message'].get('content'))!=entry['report']:
                raise b.ShrinkError('Actual full acoustic raw response differs from its selected report.')
            payloads.append({'part':index,'window':window,'complete_report':entry['report'],'source':entry['source_info'],
                'output':entry['output_info'],'raw_sha256':b.sha(raw),'actual_part_sha256':part['sha256']})
    b.command(['ffmpeg','-v','error','-i',result['audio'],'-f','null','-'])
    words=b.read(directory/'navigation.json');removed=set().union(*(set(range(c['first_word'],c['last_word']+1)) for c in edit['cuts']))
    return result,{'result_sha256':b.sha(directory/'result.json'),'input_sha256':original['master']['sha256'],
        'audio_sha256':result['audio_sha256'],'all_part_sha256s':[v['sha256'] for v in parts],
        'complete_audio_payload_fingerprint':b.fingerprint(payloads),'source_navigation_fingerprint':b.fingerprint(words),
        'retained_word_ids_fingerprint':b.fingerprint([w['id'] for w in words if w['id'] not in removed]),
        'complete_windows':len(payloads),'complete_parts':len(parts),'no_delivery_performed':True}


def parse_send_receipt(stdout,target):
    decoder=json.JSONDecoder();candidates=[]
    for match in re.finditer(r'\{',stdout):
        try:value,_=decoder.raw_decode(stdout[match.start():])
        except ValueError:continue
        if isinstance(value,dict) and value.get('action')=='send':candidates.append(value)
    if len(candidates)!=1:raise b.ShrinkError('Send returned no unique complete platform receipt; delivery is uncertain.')
    value=candidates[0];payload=value.get('payload',{});message_id=value.get('messageId')
    if (value.get('channel')!='whatsapp' or value.get('dryRun') is not False or not isinstance(message_id,str) or not message_id.strip()
        or payload.get('to')!=target or payload.get('deliveryStatus') in ('failed','suppressed','queued')):
        raise b.ShrinkError('Send was dry-run, unconfirmed, failed or for another destination; do not repeat it.')
    return value


def deliver(directory,target,only_part=None):
    directory=Path(directory).resolve();result,proof=preflight(directory);acceptance=b.read(directory/'main-final-acceptance.json')
    if (acceptance.get('approved') is not True or acceptance.get('requesting_target')!=target
        or acceptance.get('complete_preflight_proof')!=proof or not re.fullmatch(r'\+\d{6,15}',target)):
        raise b.ShrinkError('Exact complete MAIN acceptance is missing or changed; no audio will be sent.')
    cli=shutil.which('openclaw')
    if not cli:raise b.ShrinkError('OpenClaw is missing; approved audio stays local.')
    media=Path.home()/'.openclaw/media/shrink-original'/directory.name;media.mkdir(parents=True,exist_ok=True)
    for index,part in enumerate(result['chat_audio']):
        if only_part is not None and index!=only_part:continue
        receipt=directory/f'delivery-{index:03d}.json';signature=b.fingerprint({'target':target,'part':part['sha256']})
        if receipt.exists():
            old=b.read(receipt)
            if old.get('fingerprint')==signature and old.get('status')=='sent':continue
            raise b.ShrinkError('An earlier delivery is uncertain; no automatic resend.')
        actual=media/f'part-{index+1:03d}.ogg';shutil.copy2(part['path'],actual)
        if b.sha(actual)!=part['sha256']:raise b.ShrinkError('Published media copy changed before send.')
        caption=(f"{result['title']} — /shrink\nOriginal voices; {result['duration_seconds']/60:.1f} min, "
            f"{result['reduction_fraction']:.0%} shorter. Three small false-start cuts and gentle 1.08× tempo, not a summary. "
            f"Part {index+1}/{len(result['chat_audio'])}. Source/output checked; claims not independently fact-checked.")
        b.save(receipt,{'fingerprint':signature,'status':'sending','actual_media_sha256':b.sha(actual),'target':target})
        try:
            sent=subprocess.run([cli,'message','send','--channel','whatsapp','--target',target,'--media',str(actual),'--message',caption,'--json'],
                capture_output=True,text=True,timeout=180)
            evidence={'exit_code':sent.returncode,'stdout':sent.stdout,'stderr':sent.stderr}
            for key,secret in b.os.environ.items():
                if re.search('KEY|TOKEN|PASSWORD|SECRET',key,re.I) and len(secret)>=4:
                    evidence={k:v.replace(secret,'<redacted>') if isinstance(v,str) else v for k,v in evidence.items()}
            b.save(directory/f'delivery-{index:03d}-cli.json',evidence)
            if sent.returncode:raise b.ShrinkError('Platform send failed; its uncertain receipt is preserved, not retried.')
            platform=parse_send_receipt(sent.stdout,target)
            b.save(receipt,{'fingerprint':signature,'status':'sent','actual_media_sha256':b.sha(actual),
                'platform_message_id':platform['messageId'],'platform_receipt':platform,'at':time.time()})
            print({'part':index+1,'status':'sent','platform_message_id':platform['messageId']},flush=True)
        except Exception as error:
            b.save(receipt,{'fingerprint':signature,'status':'uncertain','error':str(error) if isinstance(error,b.ShrinkError) else type(error).__name__})
            raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True)
    parser.add_argument('--target');parser.add_argument('--only-part',type=int)
    args=parser.parse_args()
    if args.target:deliver(Path(args.directory),args.target,args.only_part)
    else:print(json.dumps(preflight(Path(args.directory))[1],ensure_ascii=False,indent=2))
