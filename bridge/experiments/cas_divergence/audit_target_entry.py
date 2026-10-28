#!/usr/bin/env python3
"""Recheck target-entry probes against retained native baselines."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from run_repair import PINS,SYSTEM
from verify_target_entry import compare

HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--builds',nargs=6,type=Path,required=True);p.add_argument('--baselines',nargs=8,type=Path,required=True)
    p.add_argument('--runs',nargs=24,type=Path,required=True)
    for key in ('original-listing','decoder','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required')
    targets=(0x298,0x2b8,0x330);patterns=(0,2,3,4)
    pins={0x298:'9bd7ad3485beba2bc3b4a9eb7fc43e514ecbe0b8613b7fc81c8ad0a659fe4227',
          0x2b8:'24c90474d293c99f1fe7fe4013397d9a1b76867730834e55c1477351441bb46b',
          0x330:'b80ec4b85bccfb3a621d220a462b41636228ffc26a82b6de539679f2a4bf7604'}
    builds=[x.resolve() for x in a.builds];hosts=set()
    for i,build in enumerate(builds):
        target=targets[i%3];m=json.loads((build/'build.json').read_text());need(m['target']==target,'target differs')
        for name,digest in m['files_SHA256'].items():need(sha(build/name)==digest,'build differs: '+name)
        old=(build/'original.sass').read_bytes();new=(build/'trace.sass').read_bytes()
        need(sha(build/'shader.metallib')==PINS['shader.metallib'] and sha(build/'original.sass')==PINS['original.sass'] and
             sha(build/'trace.sass')==pins[target] and sha(build/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
             sha(build/'KeplerNativeCAS.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
             sha(build/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
             sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),'profile differs')
        for name in ('branch_witness_host.mm','cb0_readback_import.mm'):need(sha(build/name)==sha(HERE/name),'host source differs')
        need(len(new)==len(old)+128 and [j for j in range(0,len(old),8) if old[j:j+8]!=new[j:j+8]]==[target,0x528] and
             old[0x290:0x298]==new[0x290:0x298] and new[0x550:0x558]==old[target:target+8] and
             new[0x590:0x598]==old[0x528:0x530] and verify_decoder(old,a.original_listing.read_text(),a.decoder) and
             verify_decoder(new,(build/'trace.asm').read_text(),a.decoder),'code or replay differs')
        hosts.add(sha(build/'host'))
    need(len(hosts)==1,'hosts differ')
    def read(root,mode,pattern,build=None):
        root=root.resolve();m=json.loads((root/'manifest.json').read_text());r=json.loads((root/'report.json').read_text());args=m['arguments']
        need(m['mode']==mode and m['pattern']==pattern and m['exit_code']==0 and m['GPU_reservation']['state']=='terminal' and
             not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['system_before']==m['system_after']==SYSTEM and
             m['original_binary_sha256'] in hosts and m['signed_binary_sha256']==sha(root/'application') and
             (build is None or m['build_sha256']==sha(build/'build.json')),'process differs')
        need(len(args)==7 and args[1]==mode and args[6]==str(pattern) and sha(Path(args[2]))==PINS['shader.metallib'] and
             sha(Path(args[3]))=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
             sha(Path(args[4]))==PINS['original.sass'] and sha(Path(args[5]))==(PINS['original.sass'] if mode=='baseline' else pins[m['target']]),
             'process inputs differ')
        need(subprocess.run(['codesign','--verify','--strict',str(root/'application')],capture_output=True,timeout=15).returncode==0,'signature differs')
        proof=r['import'];events=proof['events']
        need(proof['contract_verified'] and proof['constructor_restored'] and len(events)==1 and
             events[0]['conditional_auxiliary_section_pinned'] and events[0]['expected_original_code_identical'] and
             events[0]['native_metadata_identical_to_certificate'] and events[0]['imported_code_identical'] and
             events[0]['native_metadata_preserved_except_instruction_count'] and events[0]['code_input_unchanged_after_constructor'],
             'constructor evidence differs')
        return (root/'output.bin').read_bytes(),r,(m['started_at'],m['completed_at'])
    baselines=[]
    for cohort in range(2):
        baselines.append([read(a.baselines[cohort*4+i],'baseline',pattern) for i,pattern in enumerate(patterns)])
    receipts=[];intervals=[];matrices=[]
    for cohort in range(2):
        matrix={}
        for t,target in enumerate(targets):
            build=builds[cohort*3+t];row={}
            for i,pattern in enumerate(patterns):
                raw,report,interval=read(a.runs[cohort*12+t*4+i],'trace',pattern,build)
                baseline,breport,_=baselines[cohort][i];result=compare(baseline,breport,raw,report)
                need(result['status']=='PASS','output differs');row[str(pattern)]=result['markers'];intervals.append(interval)
                receipts.append({'cohort':cohort+1,'target':hex(target),'pattern':pattern,'markers':result['markers'],
                                 'baseline_sha256':result['baseline_sha256'],'trace_sha256':result['trace_sha256']})
            matrix[hex(target)]=row
        matrices.append(matrix)
    need(matrices[0]==matrices[1],'cohort matrices differ')
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'trace processes overlap')
    result={'status':'PASS','matrix':matrices[0],'cohorts':2,'trace_processes':24,'rows_per_process':99,
            'prior_baseline_processes':8,'receipts':receipts,'original_indirect_instruction_preserved_in_import':True,
            'entry_marker_means_indirect_origin':False,'resident_instructions_read_back':False,
            'general_indirect_control_flow_proved':False,'performance_benchmark':False}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
