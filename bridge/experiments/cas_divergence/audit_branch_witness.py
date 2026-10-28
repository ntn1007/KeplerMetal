#!/usr/bin/env python3
"""Recheck two branch-register witness cohorts and bounded GPU outputs."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from run_repair import PINS,SYSTEM
from verify_branch_witness import compare

HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--builds',nargs=2,type=Path,required=True);p.add_argument('--runs',nargs=16,type=Path,required=True)
    for name in ('original-listing','decoder','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required')
    builds=[x.resolve() for x in a.builds];pinned='9bdfd7b796935448277cdeacfc0102633388eb46eaf6ef2b7e020125653bc7db'
    for build in builds:
        manifest=json.loads((build/'build.json').read_text())
        for name,digest in manifest['files_SHA256'].items():need(sha(build/name)==digest,'build differs: '+name)
        need(sha(build/'shader.metallib')==PINS['shader.metallib'] and sha(build/'original.sass')==PINS['original.sass'] and
             sha(build/'trace.sass')==pinned and sha(build/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
             sha(build/'KeplerNativeCAS.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
             sha(build/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
             sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),'profile differs')
        for name in ('branch_witness_host.mm','cb0_readback_import.mm'):need(sha(build/name)==sha(HERE/name),'host source differs')
        old=(build/'original.sass').read_bytes();new=(build/'trace.sass').read_bytes()
        need(len(new)==len(old)+128 and [i for i in range(0,len(old),8) if old[i:i+8]!=new[i:i+8]]==[0x290,0x528] and
             new[0x590:0x598]==old[0x528:0x530] and verify_decoder(old,a.original_listing.read_text(),a.decoder) and
             verify_decoder(new,(build/'trace.asm').read_text(),a.decoder),'witness code differs')
    need(sha(builds[0]/'host')==sha(builds[1]/'host'),'rebuilt hosts differ')
    receipts=[];intervals=[];expected={0:'1',2:'152',3:'184',4:'48'}
    for cohort in range(2):
        build=builds[cohort]
        for pos,pattern in enumerate((0,2,3,4)):
            results=[]
            for phase,mode in enumerate(('baseline','trace')):
                root=a.runs[cohort*8+pos*2+phase].resolve();manifest=json.loads((root/'manifest.json').read_text());r=json.loads((root/'report.json').read_text())
                need(manifest['mode']==mode and manifest['pattern']==pattern and manifest['exit_code']==0 and
                     manifest['GPU_reservation']['state']=='terminal' and not manifest['SIGKILL_requested'] and
                     not manifest['authoritative_ps_status'] and manifest['system_before']==manifest['system_after']==SYSTEM and
                     manifest['build_sha256']==sha(build/'build.json') and manifest['original_binary_sha256']==sha(build/'host') and
                     manifest['signed_binary_sha256']==sha(root/'application'),'process differs')
                args=manifest['arguments'];need(len(args)==7 and args[1]==mode and args[6]==str(pattern) and
                    Path(args[5]).name==('original.sass' if mode=='baseline' else 'trace.sass'),'program selection differs')
                need(subprocess.run(['codesign','--verify','--strict',str(root/'application')],capture_output=True,timeout=15).returncode==0,'signature differs')
                proof=r['import'];events=proof['events']
                need(proof['contract_verified'] and proof['constructor_restored'] and len(events)==1 and
                     events[0]['conditional_auxiliary_section_pinned'] and events[0]['expected_original_code_identical'] and
                     events[0]['native_metadata_identical_to_certificate'] and events[0]['imported_code_identical'] and
                     events[0]['native_metadata_preserved_except_instruction_count'] and events[0]['code_input_unchanged_after_constructor'],
                     'constructor evidence differs')
                results.append(((root/'output.bin').read_bytes(),r));intervals.append((manifest['started_at'],manifest['completed_at']))
            result=compare(*results[0],*results[1]);need(result['status']=='PASS' and result['markers']=={expected[pattern]:99},'observed marker differs')
            receipts.append({'cohort':cohort+1,'pattern':pattern,'rows':99,'marker':expected[pattern],
                             'baseline_sha256':result['baseline_sha256'],'trace_sha256':result['trace_sha256']})
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(15)),'process overlap')
    result={'status':'PASS','cohorts':2,'receipts':receipts,'GPU_processes':16,'GPU_rows':1584,
            'marker_scope':'low byte of register immediately before relocated indirect branch',
            'branch_target_entry_proved':False,'unmodified_shader_branch_proved':False,
            'resident_instructions_read_back':False,'all_paths_qualified':False,'performance_benchmark':False}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
