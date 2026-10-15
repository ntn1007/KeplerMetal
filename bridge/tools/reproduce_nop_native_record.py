#!/usr/bin/env python3
"""Prepare the native resource state without running the recorded user kernel."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-4000:]
base=(ROOT/'tools/native_replay_probe.mm').read_text();needle='[original writeToFile:[dir stringByAppendingPathComponent:@"original.commands.bin"] atomically:YES];[e endEncoding];'
assert base.count(needle)==1
replacement=r'''[original writeToFile:[dir stringByAppendingPathComponent:@"original.commands.bin"] atomically:YES];
 // Replace only the recorded launch by a legal PGRAPH NOP in OUR encoder.
 uint32_t header=0,value=0;memcpy(&header,(const char*)original.bytes+448,4);if((header&0x1fff)!=(0x2bc/4)||word(original,448)!=0x00000003200120afULL)return 20;header=(header&~0x1fffu)|(0x100/4);memcpy((void*)(before.current+448),&header,4);memcpy((void*)(before.current+452),&value,4);
 [readMemory(before.current,464)writeToFile:[dir stringByAppendingPathComponent:@"record-preparation.commands.bin"] atomically:YES];[e endEncoding];'''
base=base.replace(needle,replacement,1);base=base.replace('if(referenceCount!=local*groups)return 8;','if(referenceCount!=0)return 8;for(size_t i=0;i<hostOut.length;i++)if(((const uint8_t*)hostOut.contents)[i]!=0xa5)return 8;',1)
base=base.replace('@"reference_native_invocations":@(referenceCount)','@"reference_native_invocations":@(referenceCount),@"record_preparation_user_kernel_executed":@NO',1)
source=out/'nop_native_record_probe.mm';source.write_text(base);sources=[source]
for name in ['KeplerNativeCommands.h','KeplerNativeCommands.mm']:
 f=out/name;f.write_bytes((ROOT/'src'/name).read_bytes());sources.append(f)
library=out/'indirect_compute_probe.metallib';library.write_bytes((ROOT/'results/indirect-compute-native-qualified'/library.name).read_bytes());exe=out/'nop_native_record_probe'
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());(out/'inputs.json').write_text(json.dumps({'source_hashes':{x.name:sha(x) for x in sources},'library_SHA256':sha(library),'Git_commit':None,'Qwen_job_ids':[],'system_modifications':False},indent=2)+'\n')
run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(source),str(out/'KeplerNativeCommands.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
dest=out/'outputs';dest.mkdir();execution=out/'execution';run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','20','--',str(library),str(dest),'execute','33','3'],'observe')
process=json.loads((execution/'manifest.json').read_text());assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'];result=json.loads((execution/'execution.stdout').read_text());(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');assert result['passed'] and result['reference_native_invocations']==0;print(json.dumps({'record_preparation_kernel_invocations':0,'replay_trials':len(result['runs']),'all_children_terminal':True},indent=2))
