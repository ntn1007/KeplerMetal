#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Map recorded GVA return offsets to current-cache function starts; no execution."""
import argparse,bisect,hashlib,json,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]/'tools'))
from inspect_video_cache import Cache,image_map,inspect
IMAGE='/System/Library/PrivateFrameworks/AppleGVA.framework/Versions/A/AppleGVA';UUID='ca5414f369373c059ea2d82b35afd4f0'
EXPECTED=[(152101,151999,213,'d5a78812a5224dc620e0b9fddd2c2c4422a2399e18f994d67a10885f0b88a15b'),(149133,148746,2669,'f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19'),(117072,117024,176,'c4ef1c90c52e607a307e995c036890376ebf959ba9ade05725ff02c5cc1b7273'),(232932,232918,136,'80adc25382ccad971d4388af6ab616ae65200ab934d6819a7cbd54c9efdba68f'),(115492,115359,719,'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c'),(264163,262270,2452,'2ce45fe6c3ffc591e794e46655393ba2848540f55c891bfbf1f189e6d0e4c9e0')]
def need(x,msg):
 if not x:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--host',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');host=a.host.resolve();trace=(host/'execution/execution.stderr').read_text();need(trace.count('KM_STACK count=6 offsets='+','.join(str(x[0]) for x in EXPECTED))==1 and 'KM_BOARD mode=gva profile=1 type=1 valid=1' in trace,'stack witness differs');m=json.loads((host/'execution/manifest.json').read_text());need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal','host not terminal')
 cache=a.cache.resolve();mapped=image_map(cache.with_name(cache.name+'.map'),IMAGE);base=mapped[0]['start'];c=Cache(cache);image,starts=inspect(c,base,IMAGE);need(image['UUID']==UUID,'cache image differs');rows=[]
 for ret,want_start,want_size,want_hash in EXPECTED:
  target=base+ret-1;ix=bisect.bisect_right(starts,target)-1;need(0<=ix<len(starts)-1,'function boundary unavailable');begin,end=starts[ix:ix+2];payload=c.read(begin,end-begin);h=hashlib.sha256(payload).hexdigest();need((begin-base,len(payload),h)==(want_start,want_size,want_hash),'cache region differs');call=c.read(base+ret-5,5);target_offset=ret+struct.unpack_from('<i',call,1)[0] if call[0]==0xe8 else None;rows.append({'return_offset':ret,'cache_function_start':want_start,'cache_function_bytes':want_size,'cache_region_SHA256':h,'static_direct_call_target':target_offset})
 need(rows[1]['static_direct_call_target']==rows[0]['cache_function_start'] and rows[2]['static_direct_call_target']==rows[1]['cache_function_start'] and rows[3]['static_direct_call_target']==rows[2]['cache_function_start'],'direct call chain differs')
 result={'status':'STATIC_AND_RECORDED_STACK','image_UUID':UUID,'rows':rows,'live_code_identity_proved_for_every_frame':False,'stack_complete':False,'vendor_program_executed_during_mapping':False,'system_modified':False};
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
