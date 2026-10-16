#!/usr/bin/env python3
"""Native arm64 reference runner for the source-only control-flow bundle."""
from pathlib import Path
import argparse,hashlib,json,platform,shutil,subprocess
from run_sdk_host import run_host
ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metallib',type=Path);p.add_argument('--metallib-sha256');a=p.parse_args()
    if bool(a.metallib)!=bool(a.metallib_sha256):p.error('Provide both the explicit library and its SHA256')
    manifest=json.loads((ROOT/'FILE_MANIFEST.json').read_text())
    assert platform.machine()=='arm64'
    for row in manifest['files']:assert sha(ROOT/row['path'])==row['SHA256']
    out=ROOT/'build';out.mkdir(exist_ok=False);(out/'assets').mkdir();commands=[]
    steps=[]
    if a.metallib:
        assert sha(a.metallib)==a.metallib_sha256;shutil.copyfile(a.metallib,out/'assets/control_flow.metallib')
    else:steps=[('metal',['xcrun','metal','-std=macos-metal2.3','-c',ROOT/'control_flow.metal','-o',out/'control_flow.air']),('metallib',['xcrun','metallib',out/'control_flow.air','-o',out/'assets/control_flow.metallib'])]
    steps.append(('host',['xcrun','clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc',ROOT/'control_flow_reference.mm','-framework','Metal','-framework','Foundation','-o',out/'application']))
    for name,cmd in steps:
        cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr);commands.append({'label':name,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-2500:];print(name,'PASS',flush=True)
    (ROOT/'results').mkdir(exist_ok=False);history=[]
    for mode in ['depth0','depth64','depth96','no_dispatch:depth96']:
        target=ROOT/'results'/mode.replace(':','-');target.mkdir();(target/'outputs').mkdir();(target/'assets').mkdir()
        shutil.copyfile(ROOT/'control_flow_reference.mm',target/'control_flow_reference.mm');shutil.copyfile(ROOT/'control_flow.metal',target/'control_flow.metal');shutil.copyfile(out/'assets/control_flow.metallib',target/'assets/control_flow.metallib');shutil.copyfile(out/'application',target/'application');(target/'application').chmod(0o755)
        inp={'source_hashes':{n:sha(target/n)for n in ['control_flow_reference.mm','control_flow.metal']},'assets_SHA256':{'control_flow.metallib':sha(target/'assets/control_flow.metallib')},'executable_SHA256':sha(target/'application'),'source_manifest_SHA256':sha(ROOT/'FILE_MANIFEST.json'),'architecture':'arm64','reference_target':'Apple M1 Max'}
        (target/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n')
        m=run_host(target/'application',target/'execution',[str(target/'assets'),str(target/'outputs'),mode],ROOT)
        result=json.loads((target/'execution/execution.stdout').read_text());assert result['reference_target']=='Apple M1 Max'and result['native_reference']and not result['program_replaced'];(target/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        history.append({'mode':mode,'exit_code':m['exit_code'],'PID':m['pid']});(ROOT/'results/history.json').write_text(json.dumps(history,indent=2)+'\n');print(mode,'EXECUTED',flush=True)
    provenance={'architecture':'arm64','macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'clang':subprocess.check_output(['xcrun','clang++','--version'],text=True),'MSL_SHA256':sha(ROOT/'control_flow.metal'),'input_metallib_SHA256':sha(out/'assets/control_flow.metallib'),'supplied_library':bool(a.metallib),'source_manifest_SHA256':sha(ROOT/'FILE_MANIFEST.json'),'job_ids':[],'system_modified':False,'performance_benchmark':False}
    (ROOT/'results/provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    (ROOT/'RESULT_MANIFEST.json').write_text(json.dumps({'files':{str(f.relative_to(ROOT)):sha(f)for f in sorted(ROOT.rglob('*'))if f.is_file()and f.name!='RESULT_MANIFEST.json'}},indent=2)+'\n')
    print('REFERENCE EXECUTIONS FINISHED; numeric verification is separate',flush=True)
if __name__=='__main__':main()
