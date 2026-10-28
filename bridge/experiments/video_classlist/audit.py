#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the pinned on-disk RM class-list provenance; never call RM."""
import argparse,hashlib,json,re,struct,subprocess,sys,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parents[1]/'tools'))
from compare_video_profile import file_bytes,symbols_and_external_relocations

DRIVER='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
REA='1298e571fa38a96d99a8b20f67e6dd5ac5f55f312ee0c7decaff4d25e4e9050c'
HEADERS={'ctrl0080gpu-515.h':'b3d04542cc1f353bd86667111b74da7b676e1039c1c6634418cf80295d9d52bc','nvtypes-515.h':'202dce9a08a910137078289fc2219e70fab883503b5ee7b6a2397a8ce5564c5c','ctrl0080gpu.h':'63501de37b90eac1f4b966c8f90e9e4cb3ac1696f7c479e9a33fe86ea4bd18fd'}
FUNCS={'init_class_list':(0xc842,0xc957,'8e23698868d379e51a167aba139aa24b5c5dba7e6533740670a224bb3c865ee4','__ZN13nvAccelerator13InitClassListEv','ev_a1eeaa10ab9299e94ad109b2760ee9c3390925aaf775cdb4cfc639123d8e6ebc'), 'initialize_device':(0x93dc,0x964e,'146a60a8a1985ca284682be4c8f9fafb36a558b187947ef3d93ddce760b52bbb','__ZN13nvAccelerator16InitializeDeviceEv','ev_d8f7af523728ae987aee4a1891b6d71cd7f60779ab314cd82396957fe334d5e1')}
SITES={0xc852:'488d4de0',0xc856:'488919',0xc86d:'8919',0xc86f:'48895908',0xc886:'ba01028000',0xc88b:'41b810000000',0xc8a5:'8b55e0',0xc8a8:'41899668160000',0xc8af:'48c1e202',0xc8e6:'49898660160000',0xc8f1:'48894108',0xc908:'ba01028000',0xc90d:'41b810000000',0xc932:'49899e60160000',0xc939:'41c7866816000000000000'}
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check_sites(data):
 for addr,hexbytes in SITES.items():
  _,b=file_bytes(data,addr,len(bytes.fromhex(hexbytes)));need(b==bytes.fromhex(hexbytes),'instruction '+hex(addr))
 for site,target in [(0x9568,0xc842),(0x9588,0xca6e)]:
  _,b=file_bytes(data,site,5);need(b[0]==0xe8 and site+5+struct.unpack_from('<i',b,1)[0]==target,'device init call '+hex(site))
def declaration(text):
 need(re.search(r'#define\s+NV0080_CTRL_CMD_GPU_GET_CLASSLIST\s+\(0x800201\)',text),'NVIDIA command')
 rows=re.findall(r'typedef struct NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS\s*\{\s*NvU32 numClasses;\s*NV_DECLARE_ALIGNED\(NvP64 classList, 8\);\s*\}\s*NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS;',text)
 need(len(rows)==1,'NVIDIA structure');return rows[0]
def compile_layout(reference,out_parent):
 types=(reference/'nvtypes-515.h').read_text();need('typedef void*              NvP64;' in types and '#define NV_DECLARE_ALIGNED(TYPE_VAR, ALIGN) TYPE_VAR __attribute__ ((aligned (ALIGN)))' in types,'NVIDIA type anchors')
 old=declaration((reference/'ctrl0080gpu-515.h').read_text());new=declaration((reference/'ctrl0080gpu.h').read_text());need(old==new,'header declarations differ')
 # Extract only the public declaration to a disposable build. Standard uint32_t
 # models NvU32 and the pinned 64-bit typedef/macro are checked above.
 program='#include <stdint.h>\n#include <stddef.h>\n#include <stdio.h>\ntypedef uint32_t NvU32;\ntypedef void* NvP64;\n#define NV_DECLARE_ALIGNED(TYPE_VAR, ALIGN) TYPE_VAR __attribute__ ((aligned (ALIGN)))\n'+old+'\n_Static_assert(sizeof(void*)==8,"pointer");\n_Static_assert(sizeof(NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS)==16,"size");\n_Static_assert(offsetof(NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS,numClasses)==0,"count");\n_Static_assert(offsetof(NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS,classList)==8,"pointer offset");\nint main(void){puts("layout16 count0 pointer8");return 0;}\n'
 with tempfile.TemporaryDirectory(prefix='classlist-layout-',dir=out_parent) as t:
  source=Path(t)/'layout.c';exe=Path(t)/'layout';source.write_text(program)
  subprocess.run(['xcrun','clang','-arch','x86_64','-std=c11','-Wall','-Werror',str(source),'-o',str(exe)],capture_output=True,text=True,check=True,timeout=30)
  r=subprocess.run([str(exe)],capture_output=True,text=True,check=True,timeout=10);need(r.stdout=='layout16 count0 pointer8\n','ABI model result')
 return {'source_header_515_SHA256':HEADERS['ctrl0080gpu-515.h'],'source_nvtypes_SHA256':HEADERS['nvtypes-515.h'],'new_header_SHA256':HEADERS['ctrl0080gpu.h'],'actual_declared_struct_extracted':True,'types':'NvU32 modeled with uint32_t; NvP64 and alignment match pinned 64-bit Clang definitions','host_architecture':'x86_64','sizeof':16,'count_offset':0,'pointer_offset':8,'GPU_or_RM_call':False}
def inspect_driver(path,rea):
 data=path.read_bytes();need(hashlib.sha256(data).hexdigest()==DRIVER and sha(rea)==REA,'binary/evidence hash');syms,relocs=symbols_and_external_relocations(data);records={x['evidence_id']:x for x in json.loads(rea.read_text())['records']};out={}
 for label,(start,end,h,name,eid) in FUNCS.items():
  need(sum(s['value']==start and s['name']==name for s in syms)==1,'symbol '+label);off,b=file_bytes(data,start,end-start);need(hashlib.sha256(b).hexdigest()==h,'body '+label)
  r=records.get(eid);need(r and r['operation']=='analyze_function' and r['parameters']['procedure']==hex(start) and r['subject']['digest']['sha256']==DRIVER,'REA '+label)
  out[label]={'address':hex(start),'file_offset':hex(off),'bytes':len(b),'SHA256':h,'REA_evidence_id':eid}
 check_sites(data)
 for site in [0xc892,0xc914]:
  rows=relocs.get(site,[]);need(len(rows)==1 and rows[0]['external']==1 and rows[0]['pc_relative']==1 and rows[0]['type']==2 and rows[0]['symbol']['name']=='_NvRmControl','RM relocation '+hex(site))
  _,b=file_bytes(data,site-1,5);need(b==b'\xe8\0\0\0\0','unrelocated call')
 return {'driver_SHA256':DRIVER,'REA_bundle_SHA256':REA,'functions':out,'external_call_relocations':['0xc892','0xc914'],'external_symbol':'_NvRmControl','control_command':'0x800201','argument_bytes':16,'class_array_pointer_field':'0x1660','class_count_field':'0x1668','executed_or_runtime_observed':False}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--driver',type=Path,required=True);p.add_argument('--rea',type=Path,required=True);p.add_argument('--references',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output')
 for n,h in HEADERS.items():need(sha(a.references/n)==h,'NVIDIA header '+n)
 driver=inspect_driver(a.driver,a.rea);layout=compile_layout(a.references,a.out.parent)
 result={'status':'PASS_STATIC_RM_CLASSLIST_PROVENANCE','macos':driver,'nvidia_515_layout_model':layout,'nvidia_reference_515_commit':'1739a20efc4acb55fd1dc53dcc66057b70c2613c','nvidia_reference_main_commit':'ca2d03e6fafd4d4b56b383497d931c25b283bfcf','scope':'Matching numeric command and 16-byte layout are static evidence, not proof of ABI equivalence, actual class values, live call, or permission to invoke a selector.','GPU_dispatches':0,'private_RM_calls':0,'system_modified':False}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
