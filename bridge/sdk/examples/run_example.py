#!/usr/bin/env python3
"""Run a locally signed immutable application copy; never install a driver."""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess,time
SDK=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();build=a.build.resolve();out=a.out.resolve();assert not out.exists();out.mkdir(parents=True);(out/'outputs').mkdir();exe=build/'keplermetal_example'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
# Preserve executable permissions when copying the application.
for n in ['keplermetal_example','client.metallib','client.json','inputs.json']:shutil.copy2(build/n,out/n)
execution=out/'execution';execution.mkdir();signed=execution/exe.name;shutil.copy2(exe,signed);r=subprocess.run(['codesign','--force','--sign','-',str(signed)],capture_output=True,text=True,timeout=15);(execution/'sign.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
mode='execute' if a.execute else 'prepare';argv=[str(signed),str(SDK/'assets/render_state_carrier.metallib'),str(out/'client.metallib'),str(out/'client.json'),str(out/'outputs'),mode]
with (execution/'execution.stdout').open('w') as stdout,(execution/'execution.stderr').open('w') as stderr:
 child=subprocess.Popen(argv,stdout=stdout,stderr=stderr);pid=child.pid;started=datetime.datetime.now(datetime.timezone.utc).isoformat();killed=False
 try:code=child.wait(timeout=30)
 except subprocess.TimeoutExpired:
  child.kill();killed=True
  try:code=child.wait(timeout=5)
  except subprocess.TimeoutExpired:code=None
status=subprocess.run(['ps','-o','stat=,command=','-p',str(pid)],capture_output=True,text=True).stdout.strip();m={'started_at':started,'pid':pid,'arguments':argv[1:],'exit_code':code,'SIGKILL_requested':killed,'authoritative_ps_status':status if str(signed) in status else '', 'original_binary_sha256':sha(exe),'signed_binary_sha256':sha(signed),'original_executable':str(exe),'signed_executable':str(signed),'system_modified':False};(execution/'manifest.json').write_text(json.dumps(m,indent=2)+'\n');assert code==0 and not killed and not m['authoritative_ps_status'],'Own application not terminal PASS; inspect this handle before any retry'
result=json.loads((execution/'execution.stdout').read_text());(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'mode':mode,'pid':pid,'exit_code':code,'system_modified':False,'results':str(out)},indent=2))
