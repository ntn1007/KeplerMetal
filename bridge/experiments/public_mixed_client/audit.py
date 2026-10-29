#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit eight frozen mixed-client executions without launching GPU work."""
from pathlib import Path
import argparse,json,struct,subprocess,sys
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import check_library,sha,write

def need(v,m):
 if not v:raise ValueError(m)
def read(p):return json.loads(p.read_text())
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--library',type=Path,required=True);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=8,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');meta=check_library(a.library);inp=read(a.build/'inputs.json');need(meta['static_library_SHA256']==inp['library_sha256'],'runtime differs')
 need(inp['frozen']['client.mm']==sha(HERE/'client.mm') and inp['frozen']['host.mm']==sha(HERE/'host.mm') and all(sha(a.build/n)==h for n,h in inp['frozen'].items()),'build differs')
 symbols=subprocess.run(['nm','-u',str(a.build/'client.dylib')],capture_output=True,text=True,timeout=20);need(symbols.returncode==0 and 'Kepler' not in symbols.stdout and 'KPCPU' not in symbols.stdout,'client imports project')
 modes=['direct','icb','no-producer','no-render']*2;rows=[];ids=[];intervals=[];groups={}
 for path,mode in zip(a.runs,modes):
  need(read(path/'inputs.json')==inp and all(sha(path/n)==h for n,h in inp['frozen'].items()),'frozen run differs')
  m=read(path/'execution/manifest.json');d=read(path/'result.json');v=read(path/'verification.json');need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal','process unresolved')
  need(sha(path/'host')==m['original_binary_sha256'] and sha(path/'execution/application')==m['signed_binary_sha256']==m['GPU_reservation']['signed_binary_sha256'],'host signature identity')
  sign=subprocess.run(['codesign','--verify','--strict',str(path/'client.dylib')],capture_output=True,timeout=15);need(sign.returncode==0,'client signature invalid')
  need(d['status']==v['status']=='PASS' and d['mode']==v['mode']==mode and d['client']['command_status']==4 and d['device_queue_restored'] and d['shared_method_imps_unchanged'] and d['shared_methods_checked']==5,'host status')
  dev=d['device_identity'];need(dev['name']=='NVIDIA GeForce GTX 880M' and dev['PCI_vendor_id']==0x10de and dev['PCI_device_id']==0x1198,'device differs')
  events=d['scope_events'];counts={x:sum(e.get('operation')==x for e in events) for x in ['automatic_compute_encoder','automatic_render_encoder','executeCommandsInBuffer','execute_CPU_render_ICB']}
  need(counts['automatic_compute_encoder']>=1 and counts['automatic_render_encoder']>=1 and (mode=='direct' or (counts['executeCommandsInBuffer']==1 and counts['execute_CPU_render_ICB']==1)),'factory/ICB events')
  pix=(path/'outputs/pixels.bin').read_bytes();idx=(path/'outputs/indices.bin').read_bytes();ctr=(path/'outputs/counter.bin').read_bytes();need(len(pix)==49664 and len(idx)==128 and len(ctr)==132,'sizes')
  need(pix[:256]==pix[-256:]==b'\xa5'*256 and idx[:64]==b'\xa5'*64 and idx[80:]==b'\xa5'*48 and ctr[:64]==b'\xa5'*64 and ctr[68:]==b'\xa5'*64,'guard mismatch')
  producer=mode!='no-producer';draw=mode in ('direct','icb');need(struct.unpack_from('<I',ctr,64)[0]==(32 if producer else 0),'counter mismatch')
  need(struct.unpack_from('<4I',idx,64)==((0,1,2,0x4521) if producer else (0,0,0,0x77777777)),'index mismatch')
  count=0
  for y in range(48):
   for x in range(64):
    colored=draw and 3<=x<16 and 4<=y<13;count+=colored
    actual=struct.unpack_from('<4f',pix,256+16*(y*64+x));need(actual==((.75,.125,.25,1.) if colored else (0.,0.,0.,0.)),'pixel mismatch')
  need(count==v['colored_pixels'] and sha(path/'outputs/pixels.bin')==v['pixel_sha256'],'verification mismatch')
  hashes=tuple(sha(path/'outputs'/n) for n in ('pixels.bin','indices.bin','counter.bin'));groups.setdefault(mode,[]).append(hashes)
  ids.append(m['GPU_reservation']['reservation_id']);intervals.append((m['started_at'],m['completed_at']))
  rows.append({'mode':mode,'GPU_identity':dev,'reservation_id':ids[-1],'signed_host_sha256':m['signed_binary_sha256'],'client_sha256':sha(path/'client.dylib'),'pixel_sha256':hashes[0],'indices_sha256':hashes[1],'counter_sha256':hashes[2],'automatic_encoder_counts':counts,'terminal':True})
 need(all(v[0]==v[1] for v in groups.values()) and groups['direct'][0]==groups['icb'][0],'repeat/direct vs ICB differs')
 need(groups['no-producer'][0][0]==groups['no-render'][0][0] and groups['icb'][0][0]!=groups['no-render'][0][0],'negative image controls differ')
 need(len(set(ids))==8 and all(intervals[i][1]<=intervals[i+1][0] for i in range(7)),'reservations overlap')
 result={'status':'PASS_PUBLIC_MIXED_METAL_CLIENT_GPU','processes':8,'modes':modes,'checked_float_channels':8*64*48*4,'matching_direct_and_icb':True,
 'GPU_counter_per_active_process':32,'client_no_kepler_imports_checked':True,'explicit_host_scope_required':True,'unmodified_third_party_application':False,
 'full_ICB_contract':False,'system_modified':False,'performance_benchmark':False,'client_source_sha256':sha(HERE/'client.mm'),'host_source_sha256':sha(HERE/'host.mm'),
 'experiment_sha256':sha(HERE/'experiment.py'),'audit_sha256':sha(Path(__file__)),'runtime_sha256':meta['static_library_SHA256'],'rows':rows}
 write(a.out,result);print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
