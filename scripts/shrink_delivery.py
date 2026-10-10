#!/usr/bin/env python3
"""One diagnosed delivery-boundary repair; reuse only byte-identical heard inputs."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

SPEC=importlib.util.spec_from_file_location('delivery_pipeline',Path(__file__).with_name('shrink_pipeline.py'))
p=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(p)
r,b=p.r,p.b


def reusable_comparison(parent,source,output,transform,model):
    """No pass transfer across different sound, prompt, scope, model or protocol."""
    source_info,output_info=b.pcm_info(source),b.pcm_info(output)
    prompt=r.pair_prompt({k:v for k,v in source_info.items() if k!='sha256'},
        {k:v for k,v in output_info.items() if k!='sha256'},transform)
    for result_path in sorted((parent/'stages').glob('final-compare-*/result.json')):
        stage=result_path.parent;attempt=b.read(stage/'attempt.json');contract_path=stage/'comparison-contract.json'
        if not contract_path.exists():continue
        contract=b.read(contract_path)
        if contract['source_info']!=source_info or contract['output_info']!=output_info or contract['prompt']!=prompt or contract['system']!=r.PAIR_SYSTEM:continue
        report=b.read(result_path)
        try:b.require_pass(report,[])
        except b.ShrinkError:continue
        raw=stage/'openai/raw.json';http=b.read(stage/'openai/request-attempt.json');payload=b.read(raw)
        if (attempt.get('status')!='complete' or attempt.get('result_sha256')!=b.sha(result_path)
            or http.get('status')!='received' or http.get('http_status')!=200 or http.get('model')!=model or http.get('raw_sha256')!=b.sha(raw)):
            raise b.ShrinkError('A matching prior comparison has changed/incomplete receipts.')
        choices=payload.get('choices',[])
        if len(choices)!=1 or choices[0].get('finish_reason')!='stop' or b.parse_audio_text_report(choices[0]['message'].get('content'))!=report:
            raise b.ShrinkError('Matching prior raw comparison differs from its complete report.')
        return report,{'parent_stage':str(stage),'complete_attempt':attempt,'complete_contract':contract,'complete_report':report,
            'raw_sha256':b.sha(raw),'actual_source_and_output_bytes_identical':True,'request_prompt_and_system_exact':True,
            'new_container_hash_does_not_replace_window_input_proof':True,'additional_provider_requests':0}
    return None


def repair_boundary(parent,root,boundary_index=6):
    if (root/'repair-selection.json').exists():raise b.ShrinkError('This exact delivery repair already started; it will not replay.')
    parent=parent.resolve();root.mkdir(parents=True,exist_ok=True)
    edit=b.read(parent/'edit-plan.json');original=edit['source'];source=Path(b.read(parent/'source-reuse.json')['source'])
    intervals=edit['retained_intervals'];words=b.read(parent/'navigation.json');cuts=edit['cuts'];tempo=edit['binding']['tempo']
    render_parent=Path(b.read(parent/'render-reuse.json')['parent']);render=b.read(render_parent/'stages/render/result.json')
    final=Path(render['audio']).parent/'edited.wav'
    if b.pcm_info(source)!=original['master'] or b.sha(final)!=render['rendered_wav_sha256'] or b.sha(render['audio'])!=render['audio_sha256']:
        raise b.ShrinkError('Original or rendered audio changed.')
    p.verify_retained_cut(source,final.parent/'cut.wav',intervals)
    old_parts=b.read(parent/'stages/partition/result.json');frames=b.pcm_info(final)['frames']
    ranges=[[x['first_frame'],x['last_frame']] for x in old_parts]
    r.validate_partition(ranges,frames,600*b.RATE)
    hints=p.sentence_boundary_hints(source,words,intervals,tempo,frames)
    old_end=ranges[boundary_index][1]
    eligible=[h for h in hints if old_end<h['first_frame']<h['last_frame']<=old_end+8*b.RATE]
    if not eligible:raise b.ShrinkError('No strong nearby complete-sentence gap; the original failed split stays held.')
    hint=max(eligible,key=lambda h:h['last_frame']-h['first_frame'])
    new_end=r.quiet_gap_point(final,hint['first_frame'],hint['last_frame'])
    ranges[boundary_index][1]=new_end;ranges[boundary_index+1][0]=new_end
    r.validate_partition(ranges,frames,600*b.RATE)
    selection={'parent':str(parent),'parent_partition_sha256':b.sha(parent/'stages/partition/result.json'),
        'input':original,'render':render,'old_boundary':old_end,'new_boundary':new_end,'candidate_sentence_gap':hint,
        'ranges':ranges,'script_sha256':b.sha(Path(__file__)),'pipeline_sha256':b.sha(Path(__file__).with_name('shrink_pipeline.py')),
        'pair_sha256':b.sha(Path(__file__).with_name('shrink_reliable.py')),'base_sha256':b.sha(Path(__file__).with_name('shrink_original.py')),
        'one_diagnosed_boundary_repair':True,'no_new_content_cuts_or_source_changes':True,'no_delivery':True}
    b.save(root/'repair-selection.json',selection)
    b.save(root/'input.json',original);b.save(root/'edit-plan.json',edit);b.save(root/'navigation.json',words)
    client=p.EditClient(root);model=p.physical_model(intervals);parts=[]
    try:
        for index,(first,last) in enumerate(ranges):
            if [first,last]==[old_parts[index]['first_frame'],old_parts[index]['last_frame']]:
                part=old_parts[index]
                if b.sha(part['path'])!=part['sha256'] or b.sha(part['listening'])!=part['listening_sha256']:
                    raise b.ShrinkError('Unchanged outgoing media no longer matches its receipt.')
            else:
                part_root=root/'changed-parts'/str(index);pcm=part_root/'part.wav'
                receipt=r.extract_pcm(final,pcm,first,last)
                encoded=r.encode_parts(pcm,part_root/'encoded',[[0,last-first]])[0]
                part={**encoded,'first_frame':first,'last_frame':last,'global_extraction':receipt}
            actual=Path(part['listening']);info=b.pcm_info(actual);reports=[];offset=0;window=0
            while offset<info['frames']:
                stop=min(info['frames'],offset+240*b.RATE);scope=root/'comparison-inputs'/f'{index:03d}-{window:03d}'
                scope.mkdir(parents=True,exist_ok=True);src,out=scope/'source.wav',scope/'output.wav'
                r.extract_pcm(actual,out,offset,stop)
                a,z=p.source_range_for_output(model,first+offset,first+stop,tempo,original['master']['frames'])
                r.extract_pcm(source,src,a,z)
                relevant=[c for c in cuts if c['end']*b.RATE>a and c['start']*b.RATE<z]
                transform={'tempo':tempo,'removed_original_intervals':[[c['start'],c['end']] for c in relevant],
                    'source_has_extra_boundary_context':False,'source_frames':[a,z],'output_global_frames':[first+offset,first+stop],
                    'physical_scope_is_not_word_alignment':True}
                cached=reusable_comparison(parent,src,out,transform,client.openai_audio)
                if cached:
                    report,proof=cached;b.save(scope/'exact-comparison-reuse.json',proof)
                else:
                    report=b.once(root,f'final-compare-{index:03d}-{window:03d}',{'selection':b.sha(root/'repair-selection.json'),
                        'source':b.pcm_info(src),'output':b.pcm_info(out),'transform':transform,'part_sha256':part['sha256']},
                        lambda stage:client.compare(stage,src,out,transform))
                    b.require_pass(report,[])
                reports.append({'first_frame':offset,'last_frame':stop,'report':report,'source':str(src),'source_info':b.pcm_info(src),
                    'output':str(out),'output_info':b.pcm_info(out),'reused':bool(cached)})
                if stop==info['frames']:break
                offset=stop-2*b.RATE;window+=1
            parts.append({**part,'comparison_reports':reports,'review':{'pass':True,'issues':[],'uncertainties':[],
                'checked_ids':[],'protected_ids':[],'heard_start':reports[0]['report']['heard_start'],'heard_end':reports[-1]['report']['heard_end']}})
        if b.pcm_info(source)!=original['master'] or client.quota_stop:raise b.ShrinkError('Original changed or provider quota stopped.')
        result={**render,'title':original['title'],'policy':'source-relative-delivery-repair-v1','source_seconds':original['master']['seconds'],
            'reduction_fraction':1-render['duration_seconds']/original['master']['seconds'],'cut_count':len(cuts),'chat_audio':parts,
            'automatic_reviews_passed':True,'human_listening_claimed':False,'source_claims_independently_verified':False,
            'source_relative_reviews':True,'all_delivery_frames_owned_once':True,'editing_profile':'three-source-backed-restarts-and-gentle-tempo',
            'source_parent':str(parent),'one_boundary_repair':selection,'provider':client.provider}
        b.save(root/'result.json',result);return result
    except Exception as error:
        b.save(root/'hold.json',{'error':str(error) if isinstance(error,b.ShrinkError) else type(error).__name__,
            'no_further_provider_calls':True,'no_delivery':True,'old_parent_failure_preserved':True})
        raise


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__);args.add_argument('--parent',required=True);args.add_argument('--output',required=True)
    selected=args.parse_args();result=repair_boundary(Path(selected.parent),Path(selected.output))
    print(json.dumps({'duration_seconds':result['duration_seconds'],'cut_count':result['cut_count'],'parts':len(result['chat_audio']),
        'reused_windows':sum(x['reused'] for part in result['chat_audio'] for x in part['comparison_reports']),'no_delivery':True}))
