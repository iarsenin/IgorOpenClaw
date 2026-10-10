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
        r.require_comparison_decision(entry);previous=last
    if previous!=frames:raise b.ShrinkError('Final actual audio samples were not all reviewed.')


def preflight(directory):
    directory=Path(directory).resolve();result=b.read(directory/'result.json')
    if result.get('policy')==p.POLICY:return preflight_pipeline(directory,result)
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


def preflight_pipeline(directory,result):
    """Complete current-pipeline gates; old case-specific approvals cannot transfer."""
    source=Path(result['source_path']);original=b.read(directory/'input.json');edit=b.read(directory/'edit-plan.json')
    final=Path(result['audio']).parent/'edited.wav'; cuts=edit['cuts']; intervals=edit['retained_intervals']
    if (not result.get('source_relative_reviews') or edit['source']!=original
        or b.pcm_info(source)!=original['master'] or b.sha(result['audio'])!=result['audio_sha256']
        or b.sha(final)!=result['rendered_wav_sha256']):
        raise b.ShrinkError('Current source, edit or final media changed before publication.')
    p.verify_retained_cut(source,final.parent/'cut.wav',intervals)
    expected=[];cursor=0
    for cut in sorted(cuts,key=lambda c:c['start']):
        if not cursor<=cut['start']<cut['end']<=original['master']['seconds']:raise b.ShrinkError('Invalid or overlapping cuts.')
        if cursor<cut['start']:expected.append([cursor,cut['start']])
        cursor=cut['end']
    if cursor<original['master']['seconds']:expected.append([cursor,original['master']['seconds']])
    if intervals!=expected:raise b.ShrinkError('Retained media intervals do not match the reviewed cut list.')
    b.require_pass(result['text_report'],[c['id'] for c in cuts],[v['id'] for v in edit['plan']['protected']])
    p.verify_raw_report(result['text_evidence'],result['text_report'],audio=False)
    text_attempt=b.read(Path(result['text_evidence']['stage'])/'attempt.json')
    if text_attempt['binding']['input']!=original or text_attempt['binding']['plan']!=b.fingerprint(edit['plan']):
        raise b.ShrinkError('Independent text review belongs to another source or plan.')
    if len(result['join_evidence'])!=len(cuts):raise b.ShrinkError('A proposed cut has no actual-audio review.')
    for item,cut in zip(result['join_evidence'],cuts):
        b.require_pass(item['report'],[]);p.verify_raw_report(item['proof'],item['report'])
        stage=Path(item['proof']['stage']);contract=b.read(stage/'edit-comparison-contract.json')
        attempt=b.read(stage/'attempt.json');proposal=contract['proposal']
        if (proposal!=attempt['binding']['proposal'] or
            proposal['provisional_cut']!={k:cut[k] for k in ('id','kind','start','end','first_word','last_word')}):
            raise b.ShrinkError('Join review belongs to another cut.')
        index=cuts.index(cut);src=directory/'joins'/str(index)/'source.wav';out=directory/'joins'/str(index)/'output.wav'
        if b.pcm_info(src)!=contract['source'] or b.pcm_info(out)!=contract['output']:
            raise b.ShrinkError('Reviewed join inputs changed.')
        p.prove_source_clip(source,src,proposal['source_first_frame'],proposal['source_last_frame']-proposal['source_first_frame'])
        physical=p.physical_model(intervals)
        following=[piece['cut_first'] for piece in physical if piece['source_first']>=round(cut['end']*b.RATE)]
        join=min(following) if following else physical[-1]['cut_last']
        first=max(0,round((join-8*b.RATE)/result['tempo']))
        last=min(b.pcm_info(final)['frames'],round((join+8*b.RATE)/result['tempo']))
        p.prove_source_clip(final,out,first,last-first)
    frames=b.pcm_info(final)['frames'];parts=result['chat_audio'];model=p.physical_model(intervals);payloads=[]
    r.validate_partition([[v['first_frame'],v['last_frame']] for v in parts],frames,600*b.RATE)
    for part in parts:
        audio,listen=Path(part['path']),Path(part['listening'])
        if (b.sha(audio)!=part['sha256'] or b.sha(listen)!=part['listening_sha256'] or audio.stat().st_size>14*1024*1024
            or b.pcm_info(listen)['frames']!=part['last_frame']-part['first_frame']):
            raise b.ShrinkError('Actual outgoing media changed or is incomplete/oversized.')
        extraction=part['extraction']
        if (extraction['source_sha256']!=b.sha(final) or extraction['first_frame']!=part['first_frame']
            or extraction['last_frame']!=part['last_frame']):raise b.ShrinkError('Outgoing part extraction has different ownership.')
        p.prove_source_clip(final,Path(extraction['output']),part['first_frame'],part['last_frame']-part['first_frame'])
        with tempfile.TemporaryDirectory(prefix='shrink-preflight-') as temp:
            decoded=Path(temp)/'actual.wav'
            b.command(['ffmpeg','-v','error','-n','-i',audio,'-ar',b.RATE,'-ac','1','-c:a','pcm_s16le',decoded])
            if b.pcm_info(decoded)!=b.pcm_info(listen):raise b.ShrinkError('The outgoing file is not the reviewed decode.')
        validate_windows(part['comparison_reports'],part['last_frame']-part['first_frame'])
        for entry in part['comparison_reports']:
            src,out=Path(entry['source']),Path(entry['output']);a,z=entry['source_frames']
            if b.pcm_info(src)!=entry['source_info'] or b.pcm_info(out)!=entry['output_info']:
                raise b.ShrinkError('A complete reviewed input changed.')
            first,last=part['first_frame']+entry['first_frame'],part['first_frame']+entry['last_frame']
            if [a,z]!=list(p.source_range_for_output(model,first,last,result['tempo'],original['master']['frames'])):
                raise b.ShrinkError('A review used a different source scope.')
            p.prove_source_clip(source,src,a,z-a)
            p.prove_source_clip(listen,out,entry['first_frame'],entry['last_frame']-entry['first_frame'])
            p.verify_raw_report(entry['evidence'],entry['report'])
            contract=b.read(Path(entry['evidence']['stage'])/'comparison-contract.json')
            if contract['source_info']!=entry['source_info'] or contract['output_info']!=entry['output_info']:
                raise b.ShrinkError('Final review belongs to different audio.')
            resolution=entry.get('boundary_resolution')
            if resolution is not None:
                context=p.boundary_context(original['master']['frames'],frames,z,last,cuts)
                if context!=resolution['context']:raise b.ShrinkError('Boundary exception has no physical basis.')
                p.verify_raw_report(resolution['evidence'],resolution['report'])
                contract=b.read(Path(resolution['evidence']['stage'])/'boundary-contract.json')
                if (contract['source_info']!=entry['source_info'] or contract['output_info']!=entry['output_info']
                    or contract['original_report']!=entry['report']):raise b.ShrinkError('Boundary diagnosis belongs to another rejection.')
            payloads.append(entry)
    b.command(['ffmpeg','-v','error','-i',result['audio'],'-f','null','-'])
    return result,{'policy':p.POLICY,'result_sha256':b.sha(directory/'result.json'),
        'input_sha256':original['master']['sha256'],'all_part_sha256s':[v['sha256'] for v in parts],
        'complete_audio_payload_fingerprint':b.fingerprint(payloads),'complete_windows':len(payloads),
        'complete_parts':len(parts),'text_evidence_fingerprint':b.fingerprint(result['text_evidence']),
        'all_joins_fingerprint':b.fingerprint(result['join_evidence']),'no_delivery_performed':True}


def authorize_automatic_delivery(directory,target):
    """An explicit machine-review contract, never a fabricated MAIN/human acceptance."""
    directory=Path(directory).resolve();job=b.read(directory/'job.json')
    if (job.get('policy')!=p.POLICY or job.get('status')!='running' or job.get('target')!=target
        or job.get('code_fingerprint')!=b.release_fingerprint()):
        raise b.ShrinkError('Only the exact current running queue job can authorize automatic delivery.')
    result,proof=preflight(directory)
    if result['policy']!=p.POLICY:raise b.ShrinkError('Historical results require their original manual acceptance.')
    b.save(directory/'automatic-delivery-acceptance.json',{'policy':p.POLICY,'requesting_target':target,
        'complete_preflight_proof':proof,'code_fingerprint':b.release_fingerprint(),
        'machine_reviews_only':True,'personal_human_listening_claimed':False})


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
    directory=Path(directory).resolve();result,proof=preflight(directory)
    if result['policy']==p.POLICY:
        acceptance=b.read(directory/'automatic-delivery-acceptance.json');job=b.read(directory/'job.json')
        approved=(acceptance.get('policy')==p.POLICY and acceptance.get('machine_reviews_only') is True
            and acceptance.get('personal_human_listening_claimed') is False and job.get('status')=='running'
            and job.get('target')==target and job.get('policy')==p.POLICY
            and job.get('code_fingerprint')==acceptance.get('code_fingerprint')==b.release_fingerprint())
    else:
        acceptance=b.read(directory/'main-final-acceptance.json');approved=acceptance.get('approved') is True
    if (not approved or acceptance.get('requesting_target')!=target
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
            f"{result['reduction_fraction']:.0%} shorter. {result['cut_count']} chronological cuts and gentle {result['tempo']:.2f}× tempo, not a summary. "
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
