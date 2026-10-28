import hashlib,importlib.util,json,os,shutil,subprocess,sys,datetime
from pathlib import Path
root=Path.cwd().resolve(); work=Path(os.environ['KM_CAS_WORK']).resolve(); work.relative_to(root/'results'); mode,local,variant,name=sys.argv[1:]; local=int(local); variant=int(variant)
if mode not in ('native','native_replay','native_trampoline','native_repaired','negative_native_pin') or local not in (33,128) or variant not in (0,1) or '/' in name: raise ValueError('unsupported case')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
library=work/'test.metallib'
if sha(library)!='17cd653eb49ab7749f6013145e71292d51ce467f2a094451e6f1fc9192a31632':raise ValueError('library identity')
expected_codes={'original':'f16bf16da56d5dc060429f6886d2e1d80eafa0a960f48b7d776a3234fb6bcb41','repaired':'a193a1c62851ff483bcb3ab7fda86e9646108e36f1552f80a879616e7017e58f','trampoline':'5be52280903744eabbc4f2ca40f1560091b6c96f5ea12f73bd5b4b769018d2cc'}
for key,digest in expected_codes.items():
 if sha(work/(key+'.sass'))!=digest:raise ValueError('code identity: '+key)
exe=work/'probe'; out=work/name
if out.exists():raise ValueError('fresh output required')
module=root/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
if sha(module)!='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248':raise ValueError('reservation identity')
spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
lease=m.GPUReservation(root);child=None
try:
 out.mkdir();output=out/'outputs';output.mkdir();plan={'mode':mode,'space':'threadgroup','local':local,'groups':3,'contended':True,'variant':variant,'require_native_lock_loop':True,'layout':'noise','intent':'post_CAS_expected','library':str(library)}
 if mode!='native':
  key={'native_replay':'original','native_trampoline':'trampoline','native_repaired':'repaired','negative_native_pin':'repaired'}[mode];plan.update(original_code=str(work/('wrong-original.sass' if mode=='negative_native_pin' else 'original.sass')),code=str(work/(key+'.sass')))
  if mode=='negative_native_pin' and (work/'wrong-original.sass').read_bytes() != bytes([original_byte ^ 1 if i==0 else original_byte for i,original_byte in enumerate((work/'original.sass').read_bytes())]):raise ValueError('wrong pin construction')
 planpath=out/'plan.json';planpath.write_text(json.dumps(plan,indent=2)+'\n'); signed=out/'application';shutil.copyfile(exe,signed);signed.chmod(0o755)
 subprocess.run(['codesign','--force','--sign','-',str(signed)],check=True,capture_output=True,timeout=15);subprocess.run(['codesign','--verify','--strict',str(signed)],check=True,capture_output=True,timeout=15)
 lease.spawning(signed,sha(signed));registry=root/'results/signed-native-jobs.json';jobs=json.loads(registry.read_text()) if registry.exists() else []
 with (out/'execution.stdout').open('wb') as stdout,(out/'execution.stderr').open('wb') as stderr:
  child=subprocess.Popen([str(signed),str(planpath),str(output)],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,));lease.bind_child(child.pid)
  job={'started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'pid':child.pid,'original_executable':str(exe),'original_binary_sha256':sha(exe),'signed_executable':str(signed),'signed_binary_sha256':sha(signed),'arguments':[str(planpath),str(output)]};jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n');print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True)
  code=child.wait()
 ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
 if ps.returncode not in (0,1) or ps.stderr:raise RuntimeError('cannot verify process')
 state=ps.stdout.strip();job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat());registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
 (out/'manifest.json').write_text(json.dumps({**job,'GPU_reservation':dict(lease.data),'library_SHA256':sha(library),'runner_SHA256':sha(__file__)},indent=2)+'\n')
 print(json.dumps({'status':'TERMINAL' if not state else 'UNRESOLVED','exit_code':code,'stdout':str(out/'execution.stdout')}),flush=True)
 expected_code=4 if mode=='negative_native_pin' else 0 if mode=='native_repaired' else 10
 if state or code != expected_code:raise RuntimeError('unexpected execution; inspect process and output')
except BaseException:
 if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
 raise
finally:lease.close()
