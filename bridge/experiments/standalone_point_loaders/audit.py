#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit public Metal file/URL/data/segmented-data paths on the GTX."""
import argparse,base64,collections,hashlib,json,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
 if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def packet(x,n):
 b=base64.b64decode(x,validate=True);need(len(b)==24 and struct.unpack('<6I',b)==(0xa0050e0c,0,n,1,0,0),'draw packet differs');return b

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=27,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==27,'fresh output/distinct runs');build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build differs')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs '+n)
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build file differs '+n)
 for n in ('client.mm','bootstrap.mm'):need(sha(build/n)==sha(HERE/n),'source differs '+n)
 for n in ('application','wrong-application','bootstrap.dylib'):sign(build/n)
 imports=subprocess.run(['nm','-u',str(build/'application')],capture_output=True,text=True,timeout=20);need(imports.returncode==0 and imports.stdout==(build/'client-imports.txt').read_text() and 'Kepler' not in imports.stdout and 'KPCPU' not in imports.stdout,'client imports differ');need(b['files_sha256']['application'].encode() in (build/'bootstrap.dylib').read_bytes(),'approved client hash missing')
 expected=collections.Counter({(r,m):n for r in ('file','url','data','segmented') for m,n in (('direct',2),('auto',2),('native',1),('wrong-library',1))});expected.update({('file','wrong-client'):1,('file','wrong-manifest'):1,('file','bad-descriptor'):1});seen=collections.Counter();counts=(0,1,17,128,256);intervals=[];receipts=[];allhash=[]
 for root in a.runs:
  root=root.resolve();m=load(root/'manifest.json');mode=m['mode'];route=m['route'];seen[(route,mode)]+=1;need((route,mode) in expected and seen[(route,mode)]<=expected[(route,mode)],'unexpected cohort');inject=mode not in ('direct','native');code=0 if mode in ('direct','auto') else 3 if mode in ('wrong-client','wrong-manifest') else 8;h=b['files_sha256']['wrong-application' if mode=='wrong-client' else 'application'];lease=m['reservation']
  need(m['status']=='TERMINAL' and m['exit_code']==m['expected_exit_code']==code and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==h and m['runner_sha256']==sha(HERE/'experiment.py') and m['bootstrap_sha256']==(sha(build/'bootstrap.dylib') if inject else None),'process differs')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==code and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'lease differs');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system differ');sign(root/'application');intervals.append((m['started_at'],m['completed_at']))
  library=build/('wrong-transform.metallib' if mode=='wrong-library' else 'transform.metallib');clientmode='direct' if mode=='direct' else 'icb-bad-mask' if mode=='bad-descriptor' else 'icb';need(m['args']==[str(library),str(root/'outputs'),clientmode,route],'arguments differ');err=(root/'stderr.log').read_text();logroute='data' if route in ('data','segmented') else 'URL' if route=='url' else 'file'
  if mode in ('direct','auto'):
   obj=load(root/'stdout.json');need(obj['status']=='PASS' and obj['device']=='NVIDIA GeForce GTX 880M' and obj['registry_id'] and obj['mode']==('direct' if mode=='direct' else 'icb') and obj['route']==route and obj['segments']==({'file':0,'url':0,'data':1,'segmented':2}[route]) and obj['results']==[{'count':n,'completed':True,'guards':True,'checked_values':256} for n in counts],'client result differs')
   if mode=='auto':
    need('KM_BOOT '+logroute+' library approved' in err and 'KM_BOOT transform pipeline matched' in err and m['events_sha256']==sha(root/'events.json'),'bootstrap trace missing');events=[x for x in load(root/'events.json') if x['operation']=='execute_CPU_render_ICB'];need(len(events)==5 and events[0]['executed_indices']==[],'zero event differs')
    for n,e in zip(counts[1:],events[1:]):
     ev=e['evidence'];need(e['executed_indices']==[0] and ev['raw_records_copied']==1 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'execution differs');item=ev['sequence_records'][0];record=item['record'];raw=packet(item['commands_base64'],n);packet(item['primer_draw_base64'],1);need(item['vertex_write_usage'] and record['primitive']==0 and record['vertex_count']==n and record['direct_method']==0x3830 and record['library_SHA256']=='0bd90c4639674a1542e535b06c56a47d550f6784a2bd127278d55b0c393438ae' and hashlib.sha256(raw).hexdigest()==record['SHA256'],'record differs')
   else:need(m['events_sha256'] is None and 'KM_BOOT' not in err,'unexpected injection')
   hashes={}
   for n in counts:
    f=root/'outputs'/f'count-{n}.bin';raw=f.read_bytes();need(len(raw)==2304,'raw length differs');src,dst=raw[:1152],raw[1152:]
    for part in (src,dst):need(part[:64]==part[1088:]==b'\xa5'*64,'guard differs')
    source=tuple((i*17)^0x12345678 for i in range(256));need(struct.unpack('<256I',src[64:1088])==source and struct.unpack('<256I',dst[64:1088])==tuple(((x*3+7)&0xffffffff) if i<n else 0xa5a5a5a5 for i,x in enumerate(source)),'CPU oracle differs');hashes[str(n)]=sha(f)
   allhash.append(hashes)
  else:
   need(not list((root/'outputs').iterdir()),'negative process produced output');checks={'native':'newIndirectCommandBufferWithDescriptor:maxCount:options:','wrong-client':'KM_BOOT identity refused','wrong-manifest':'KM_BOOT transform identity refused','wrong-library':'KM_BOOT '+logroute+' library unapproved','bad-descriptor':'KM_BOOT descriptor not qualified'};need(checks[mode] in err,'negative reason differs')
   if mode in ('wrong-library','bad-descriptor'):need('Render pipeline is not owned by this scope' in err and m['events_sha256']==sha(root/'events.json') and not any(x['operation']=='execute_CPU_render_ICB' for x in load(root/'events.json')),'refusal occurred after execution')
   else:need(m['events_sha256'] is None,'unexpected scope events')
  receipts.append({'mode':mode,'route':route,'manifest_sha256':sha(root/'manifest.json'),'stdout_sha256':sha(root/'stdout.json')})
 need(seen==expected and len(allhash)==16 and all(x==allhash[0] for x in allhash),'cohort/output differs');intervals.sort();need(all(x<=y for x,y in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(26)),'overlapping processes')
 result={'status':'PASS_STANDALONE_POINT_LOADERS','archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'client_sha256':b['files_sha256']['application'],'bootstrap_sha256':b['files_sha256']['bootstrap.dylib'],'client_imports_project_symbols':False,'processes':27,'routes':['file','url','data','segmented'],'positive_processes':16,'native_icb_unavailable_controls':4,'identity_shader_descriptor_refusals':7,'raw_buffer_pairs':80,'values_checked':40960,'guard_bytes_verified':20480,'adapted_packets_verified':32,'segmented_data_regions_reported':2,'process_local_injection':True,'arbitrary_third_party_apps_qualified':False,'transparent_system_integration':False,'performance_benchmark':False,'system_files_checked_unchanged':True,'runs':receipts}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'values_checked':40960,'processes':27}))
if __name__=='__main__':main()
