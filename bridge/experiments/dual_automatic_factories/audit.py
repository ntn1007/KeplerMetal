#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck six frozen mixed GPU witnesses without submitting GPU work."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import sha,write,check_library

def need(v,m):
    if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--library',type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    meta=check_library(a.library);b=read(a.build/'inputs.json');need(meta['static_library_SHA256']==b['static_library_SHA256'],'library differs')
    need(b['source_hashes']['cpu_icb_mixed_probe.mm']==sha(HERE/'host.mm'),'host source differs')
    need(all(sha(a.build/n)==h for n,h in b['frozen'].items()),'build differs')
    original=(BRIDGE/'tools/verify_cpu_icb_mixed.py').read_text();old="d['registry_id']==4294968458"
    replacement="d['registry_id']==d['device_identity']['registry_id'] and d['device_identity']['PCI_vendor_id']==0x10de and d['device_identity']['PCI_device_id']==0x1198 and d['device_identity']['name']=='NVIDIA GeForce GTX 880M'"
    need(original.count(old)==1 and (a.build/'oracles/verify_cpu_icb_mixed.py').read_text()==original.replace(old,replacement),'oracle adjustment differs')
    modes=['execute','auto-compute-first','auto-render-first']*2;rows=[];images=None;intervals=[];ids=[]
    for path,mode in zip(a.runs,modes):
        inp=read(path/'inputs.json');m=read(path/'execution/manifest.json');d=read(path/'results.json');v=read(path/'independent-verification.json')
        need(inp==b and all(sha(path/n)==h for n,h in b['frozen'].items()),'run input differs')
        need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal','process unresolved')
        need(sha(path/'cpu_icb_mixed_probe')==m['original_binary_sha256'] and sha(path/'execution/application')==m['signed_binary_sha256'] and m['signed_binary_sha256']==m['GPU_reservation']['signed_binary_sha256'],'signed host differs')
        need(mode==d['automatic_order']==v['automatic_mode'] and d['automatic_factories']==(mode!='execute') and d['queue_restored'] and d['scope_restored'],'mode or restore differs')
        counts={n:sum(e.get('operation')==n for e in d['events']) for n in ('automatic_compute_factories_enabled','automatic_render_factories_enabled','automatic_compute_encoder','automatic_render_encoder')}
        need(all(x==0 for x in counts.values()) if mode=='execute' else counts=={'automatic_compute_factories_enabled':1,'automatic_render_factories_enabled':1,'automatic_compute_encoder':11,'automatic_render_encoder':11},'events differ')
        code='import sys,json;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from verify_cpu_icb_mixed import verify;print(json.dumps(verify(Path(sys.argv[2]),portable=True),sort_keys=True))'
        r=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,timeout=60);need(r.returncode==0,'independent oracle failed')
        proof=json.loads(r.stdout);need(proof['status']=='PASS' and proof['correct_float32_channels']==110592 and proof['GPU_compute_invocations_counted']==192,'oracle totals differ')
        hashes=[sha(path/'outputs'/('trial-%d.after.bin'%i)) for i in range(9)]
        if images is None:images=hashes
        else:need(images==hashes,'direct/automatic images differ')
        intervals.append((m['started_at'],m['completed_at']));ids.append(m['GPU_reservation']['reservation_id'])
        rows.append({'mode':mode,'signed_host_sha256':m['signed_binary_sha256'],'image_sha256':hashes,
          'automatic_compute_encoders':counts['automatic_compute_encoder'],'automatic_render_encoders':counts['automatic_render_encoder'],
          'channels':proof['correct_float32_channels'],'gpu_compute_invocations':proof['GPU_compute_invocations_counted'],
          'reservation_id':ids[-1],'process_terminal':True,'GPU_identity':d['device_identity']})
    need(len(set(ids))==6 and all(intervals[i][1]<=intervals[i+1][0] for i in range(5)),'GPU runs overlap')
    result={'status':'PASS_MIXED_AUTOMATIC_COMPUTE_RENDER_GPU','processes':6,'automatic_processes':4,'modes':modes,
      'frames':54,'checked_float_channels':663552,'gpu_compute_invocations':1152,'cross_mode_image_hashes_match':True,
      'automatic_encoder_count_includes_internal_preparation':True,'source_sha256':sha(HERE/'host.mm'),
      'experiment_sha256':sha(HERE/'experiment.py'),'audit_sha256':sha(Path(__file__)),'runtime_sha256':meta['static_library_SHA256'],
      'oracle_sha256':sha(a.build/'oracles/verify_cpu_icb_mixed.py'),'source_oracle_sha256':sha(BRIDGE/'tools/verify_cpu_icb_mixed.py'),
      'rows':rows,'unmodified_application_tested':False,'system_modified':False,'performance_benchmark':False}
    write(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
