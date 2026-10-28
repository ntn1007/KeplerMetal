#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare pinned historical macOS video components without loading them."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from compare_va_candidate import inspect_bytes,kernel_imports
from compare_video_profile import file_bytes,symbols_and_external_relocations

PINS={
 'sierra_provider':'c10e2c99d988ed42e24fd27f659d413c4f92610b2b288ac808a63dbb37277ed7',
 'high_provider':'10632d7d5e5ae6c81be6eb98045c3eb3901613434fe6f41fa1353967d60d24fd',
 'current_provider':'2d3894048f5d61f6735955211bba28cb1e1a0ff9a7f556ebb6c144018388a865',
 'sierra_ge':'25a0bccd7caa884d6aa964743b35f879ec326c46d255dc6212c47e7a20f6f38e',
 'high_ge':'bcd3d0f6d90235b1fa6e0d96904bbee829063de1b60a01362946dc8aad9a1791',
 'current_ge':'44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3',
 'high_io':'c88e2773bb11d4327e9bbbd3ef742fa84f63fad8a911dfb8cca59414ae03f267',
}
VTABLE='__ZTV14nvVideoContext';OVERRIDE='__ZN14nvVideoContext26getTargetAndMethodForIndexEPP9IOServicej';INHERITED='__ZN15IOAccelContext226getTargetAndMethodForIndexEPP9IOServicej'
def need(v,s):
 if not v:raise ValueError(s)
def load(path,digest):
 raw=Path(path).read_bytes();need(hashlib.sha256(raw).hexdigest()==digest,'input hash mismatch');return raw
def check_factory(label,row):
 expected={'sierra':(571,False,0x1f3dc),'high-sierra':(11,True,0x1e79c),'current':(11,True,0x3fa2)}
 size,stub,addr=expected[label];need(row['function_bytes']==size and row['exact_known_return_14_stub'] is stub and row['function_start']==addr,'factory profile')
 return {k:row[k] for k in ('UUID','file_SHA256','slice_SHA256','function_start','function_bytes','function_SHA256','exact_known_return_14_stub')}
def check_vtable(label,data):
 symbols,relocs=symbols_and_external_relocations(data)
 v=[x for x in symbols if x['name']==VTABLE];need(len(v)==1,'vtable symbol');address=v[0]['value'];expected={'sierra':0x87df0,'high-sierra':0x8bce8,'current':0x90fe8};need(address==expected[label],'vtable address')
 overrides=[x for x in symbols if x['name']==OVERRIDE];_,raw=file_bytes(data,address+0x950,8);value=struct.unpack('<Q',raw)[0];links=relocs.get(address+0x950,[])
 if label=='sierra':
  need(len(overrides)==1 and overrides[0]['value']==0x5f59e and value==0x5f59e and not links,'sierra override')
  target='nvVideoContext::getTargetAndMethodForIndex'
 else:
  need(not overrides and value==0 and len(links)==1,'inherited lookup identity')
  l=links[0];need(l['symbol']['name']==INHERITED and l['external']==1 and l['type']==0 and l['length_code']==3 and not l['pc_relative'],'inherited lookup relocation')
  target='IOAccelContext2::getTargetAndMethodForIndex (unresolved external relocation)'
 return {'vtable_address':hex(address),'lookup_cell':hex(address+0x950),'lookup_target':target,'live_relocation_observed':False}
def check_high_io(path,data):
 symbols,_=symbols_and_external_relocations(data);fn=[x for x in symbols if x['name']==INHERITED and x['value']==0x6e90 and x['type']&0x0e==0x0e];need(len(fn)==1,'high-sierra inherited symbol')
 off,raw=file_bytes(data,0x6e90,0x48);need(hashlib.sha256(raw).hexdigest()=='66a471167abfe05b9a0ad8ba01ec54d956b85bc635ade36ce1673448c5d9aab8','high-sierra code range')
 p=subprocess.run(['xcrun','llvm-objdump','-d','--start-address=0x6e90','--stop-address=0x6ed8',str(path)],capture_output=True,text=True,check=True,timeout=30)
 lines={}
 for line in p.stdout.splitlines():
  m=re.match(r'^\s*([0-9a-fA-F]+):\s+(?:(?:[0-9a-fA-F]{2})\s+)+(.+)$',line)
  if m:lines[int(m.group(1),16)]=re.sub(r'\s+',' ',m.group(2).split('##')[0].strip())
 for a,pattern in {0x6eb3:r'cmpl \$0x7, %edx',0x6eb6:r'ja 0x6ecb',0x6ecb:r'xorl %eax, %eax',0x6ed7:r'retq'}.items():need(a in lines and re.search(pattern,lines[a]) is not None,'lookup instruction '+hex(a))
 return {'function_address':'0x6e90','file_offset':hex(off),'length':len(raw),'function_SHA256':hashlib.sha256(raw).hexdigest(),'above_seven_static_return':'null','condition_scope':'lookup only; externalMethod fallback and live dispatch are not established'}
def audit(args):
 data={key:load(getattr(args,key),digest) for key,digest in PINS.items()}
 providers={label:check_factory(label,inspect_bytes(data[key],'_AVD_CreateAVDAccelerator')) for label,key in [('sierra','sierra_provider'),('high-sierra','high_provider'),('current','current_provider')]}
 ge={label:check_vtable(label,data[key]) for label,key in [('sierra','sierra_ge'),('high-sierra','high_ge'),('current','current_ge')]}
 imports=kernel_imports(args.high_provider,providers['high-sierra']['function_start']);sites=[hex(x['callsite']) for x in imports['scalar_call_nearby_selector_candidates'] if x['nearby_ESI_immediate']==0x105]
 need(sites==['0x2d3a2','0x2d5d9'],'high-sierra selector candidates');need(imports['static_direct_path_from_export_to_open'] is None,'unexpected direct graph path')
 return {'status':'STATIC_HIGH_SIERRA_COMPARISON_PASS','input_sha256':PINS,'factories':providers,'geforce_vtable':ge,'high_sierra_io_lookup':check_high_io(args.high_io,data['high_io']),'high_sierra_nearby_scalar_0x105_sites':sites,'high_sierra_factory_direct_path_to_open':'not found in bounded named direct call graph','limits':['No provider, driver, private selector or GPU command was executed.','Candidate immediates are not proof of live calls, connection identity or ABI.','The static lookup result alone does not prove every externalMethod fallback or runtime dispatch.','These components come from a signed update package; it is not a complete operating system image.','No hardware decode or compatibility is established.']}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for k in PINS:p.add_argument('--'+k.replace('_','-'),type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');x=audit(a)
 with a.out.open('x') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(x,sort_keys=True))
if __name__=='__main__':main()
