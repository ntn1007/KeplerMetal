#!/usr/bin/env python3
"""Rebuild the small harness/frontend for native CB1 roots; no Mesa rebuild/GPU."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/command-ir-dataflow-compiler-build-20261015'
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
m=json.loads((old/'manifest.json').read_text());assert sha(old/'air_command_compile')==m['compiler_SHA256']
for f,h in m['input_SHA256'].items():assert sha(f)==h,f
for f,h in m['fork_SHA256'].items():assert sha(old/f)==h,f
shutil.copytree(old/'source-fork',out/'source-fork')
for name in ['KeplerNativeResourceLowering.inc','KeplerResourceABI.h','command_ir_native_root_carrier.metal']:shutil.copyfile(ROOT/'src'/name,out/name)
s=(old/'air_command_compile.c').read_text()
s,n=re.subn(r'static bool lower_constants\(.*?(?=static int print_air)', '#include "KeplerNativeResourceLowering.inc"\n',s,flags=re.S);assert n==1
(out/'air_command_compile.c').write_text(s)
commands=[];build=ROOT/'build/mesa'
def run(label,args,cwd=ROOT):
 args=[str(x)for x in args];r=subprocess.run(args,cwd=cwd,capture_output=True,text=True,timeout=55);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':args,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:];print(label,'PASS',flush=True);return r.stdout
for row in json.loads((old/'commands.json').read_text()):
 if row['label'] not in ['compile-harness','compile-air_nir','link-offline']:continue
 args=[x.replace(str(old),str(out))for x in row['argv']];run(row['label'],args,build)
for n in ['producer.air','producer.metallib']:shutil.copyfile(old/n,out/n)
records=[]
for semantic in ['basic','barrier','copy','no_seed','no_gather','no_finish']:
 dest=out/semantic;dest.mkdir();raw=run('compile-'+semantic,[out/'air_command_compile',out/'producer.air',dest,'encode_dataflow_'+semantic,32,2,2]);info=json.loads(raw)
 assert info['sm']==30 and info['buffer_slots']==1 and info['grid_offset']==8 and info['push_bytes']==32 and not any(info[x]for x in ['shared_bytes','scratch_bytes','crs_bytes'])
 info.update(native_resource_abi=True,host_push_buffer_required=False,resource_cb=1,root_address_offset=8,grid_cb=1,grid_offset_native=0x720,block_offset_native=0x6f0)
 (dest/'info.json').write_text(json.dumps(info,indent=2)+'\n');records.append({'semantic':semantic,'info':info,'code_SHA256':sha(dest/'program.sass')})
run('carrier-metal',['xcrun','metal','-std=macos-metal2.0','-c',out/'command_ir_native_root_carrier.metal','-o',out/'carrier.air'])
run('carrier-metallib',['xcrun','metallib',out/'carrier.air','-o',out/'carrier.metallib'])
decoder=ROOT/'build/envydis-only/envydis/envydis'
for row in records:
 name=row['semantic'];listing=run('decode-'+name,[decoder,'-m','gf100','-V','gk104','-i','-n',out/name/'program.sass'])
 assert '???'not in listing and 'UNKNOWN'not in listing and 'INVALID'not in listing
(out/'manifest.json').write_text(json.dumps({'status':'PASS','GPU_execution':False,'compiler_SHA256':sha(out/'air_command_compile'),'native_ABI_source_SHA256':sha(out/'KeplerNativeResourceLowering.inc'),'resource_header_SHA256':sha(out/'KeplerResourceABI.h'),'source_parent_manifest_SHA256':sha(old/'manifest.json'),'producer_metallib_SHA256':sha(out/'producer.metallib'),'carrier_metallib_SHA256':sha(out/'carrier.metallib'),'records':records,'decoder_SHA256':sha(decoder),'no_Mesa_rebuild':True,'full_objective_complete':False},indent=2)+'\n')
print(json.dumps({'status':'PASS','out':str(out),'GPU_execution':False}))
