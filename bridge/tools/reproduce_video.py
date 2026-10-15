#!/usr/bin/env python3
"""Public hardware-only VideoToolbox probes, valid CPU controls and provenance."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,plistlib,subprocess

root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=root/'results/video-reproduction')
parser.add_argument('--skip-loader',action='store_true',help='Skip the separate loader observation; public codec probes still run')
args=parser.parse_args();out=args.out.resolve();out.relative_to(root/'results');out.mkdir(parents=True,exist_ok=True)
# Verify current process state, rather than trusting an old lock/status file.
life=root/'results/video-probe-lifecycle.json'
if life.exists():
    previous=json.loads(life.read_text())
    for p in previous.get('probes',[]):
        state=subprocess.run(['ps','-o','stat=,command=','-p',str(p['pid'])],capture_output=True,text=True).stdout.strip()
        if state and any(str(root/'build'/name) in state for name in ('video_loader_probe','video_engine_probe')):
            raise SystemExit('Prior native video probe remains present: '+state+'; no new video process launched')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
drivers=[Path('/System/Library/Extensions')/name/'Contents/MacOS'/name.removesuffix('.bundle') for name in ('GeForceMTLDriver.bundle','GeForceVADriver.bundle')]
before={str(p):sha(p) for p in drivers};commands=[]
assert before[str(drivers[0])]==json.loads((root/'results/macos-driver-copy.json').read_text())['sha256']
def run(command,label,environment=None):
    env=os.environ.copy()
    for key in ('KEPLER_PRELOAD_VIDEO_DRIVER','KEPLER_REGISTER_H264'):env.pop(key,None)
    if environment:env.update(environment)
    result=subprocess.run(command,cwd=root,env=env,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'label':label,'command':command,'cwd':str(root),'environment':environment or {},'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode:print(result.stderr[-3000:]);raise SystemExit(result.returncode)
    return result
run(['clang++','-O2','-std=c++17','-fno-objc-arc',str(root/'tools/video_engine_probe.mm'),'-framework','Metal','-framework','Foundation','-framework','VideoToolbox','-framework','CoreMedia','-framework','CoreVideo','-o',str(root/'build/video_engine_probe')],'probe-build')
run(['clang++','-O2','-std=c++17','-fno-objc-arc',str(root/'tools/video_loader_probe.mm'),'-framework','Foundation','-o',str(root/'build/video_loader_probe')],'loader-build')
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-Wno-deprecated-declarations',str(root/'tools/vda_engine_probe.mm'),'-framework','Foundation','-framework','VideoDecodeAcceleration','-framework','CoreVideo','-o',str(root/'build/vda_engine_probe')],'VDA-build')
run(['clang','-dynamiclib','-Wall','-Wextra','-Werror',str(root/'src/trace_iokit.c'),'-framework','IOKit','-framework','CoreFoundation','-o',str(root/'build/libTraceIOKit.dylib')],'tracer-build')
loader={'skipped':True,'hardware_execution_proved':False}
if not args.skip_loader:loader=json.loads(run([str(root/'build/video_loader_probe')],'loader').stdout)
(out/'loader.json').write_text(json.dumps(loader,indent=2)+'\n')
run(['sw_vers'],'macos');run(['xcrun','--show-sdk-version'],'sdk');run(['xcodebuild','-version'],'xcode')
run(['otool','-L',str(drivers[1])],'VA-dependencies');run(['nm','-gU',str(drivers[1])],'VA-exports')
run(['xcrun','size','-m',str(drivers[1])],'VA-sections')
run(['xcrun','llvm-objdump','--disassemble',str(drivers[1])],'VA-disassembly')
pci=subprocess.run(['/usr/sbin/ioreg','-a','-l','-r','-c','IOPCIDevice'],capture_output=True,timeout=30);assert pci.returncode==0
nodes=plistlib.loads(pci.stdout);displays=[]
def visit(n):
    cc=n.get('class-code',b'')
    if isinstance(cc,bytes) and len(cc)>=3 and (int.from_bytes(cc,'little')>>16)==3:
        displays.append({k:n[k].hex() if isinstance(n.get(k),bytes) else n.get(k) for k in ('IORegistryEntryName','IORegistryEntryID','vendor-id','device-id','class-code','model','built-in')})
    for c in n.get('IORegistryEntryChildren',[]):visit(c)
for n in nodes:visit(n)
(out/'PCI-display-inventory.json').write_text(json.dumps(displays,indent=2)+'\n')
cases=[]
specs=[('320x240',320,240,6,{}),('640x480',640,480,12,{}),('1280x720',1280,720,12,{}),
       ('preload',320,240,6,{'KEPLER_PRELOAD_VIDEO_DRIVER':'1'}),('supplemental',320,240,6,{'KEPLER_REGISTER_H264':'1'}),
       ('preload-supplemental',320,240,6,{'KEPLER_PRELOAD_VIDEO_DRIVER':'1','KEPLER_REGISTER_H264':'1'})]
for label,w,h,count,environment in specs:
    caseFolder=out/label;fixture=caseFolder/'fixture';caseFolder.mkdir(exist_ok=True)
    data=json.loads(run([str(root/'build/video_engine_probe'),str(w),str(h),str(count),str(fixture)],label,environment).stdout)
    assert data['CPU_control_valid'] and data['encode_cpu']['output_frames']==count and data['decode_cpu']['output_frames']==count
    assert data['encode_cpu']['specification']['EnableHardwareAcceleratedVideoEncoder'] is False
    assert data['decode_cpu']['specification']['EnableHardwareAcceleratedVideoDecoder'] is False
    assert data['auto_decode_comparison']['missing_frames']==0 and data['auto_decode_comparison']['different_bytes']==0
    assert data['auto_decode_comparison']['values_checked']==w*h*3//2*count
    dataPath=caseFolder/'result.json';dataPath.write_text(json.dumps(data,indent=2)+'\n')
    cases.append({'label':label,'result':str(dataPath.relative_to(root)),'environment':environment,'width':w,'height':h,'frames':count,'exit_code':0})
vdaCases=[]
for case in cases:
    for destination in ('nv12','default'):
        label=case['label']+'-VDA-'+destination;fixture=out/case['label']/'fixture'
        data=json.loads(run([str(root/'build/vda_engine_probe'),str(fixture),str(case['width']),str(case['height']),destination],label).stdout)
        path=out/(label+'.json');path.write_text(json.dumps(data,indent=2)+'\n')
        vdaCases.append({'label':label,'result':str(path.relative_to(root)),'environment':{},'exit_code':0})
traced=json.loads(run([str(root/'build/vda_engine_probe'),str(out/'320x240/fixture'),'320','240','nv12'],'VDA-trace',
                     {'DYLD_INSERT_LIBRARIES':str(root/'build/libTraceIOKit.dylib'),'KEPLER_TRACE_FILE':str(out/'VDA-iokit.jsonl')}).stdout)
(out/'VDA-trace-result.json').write_text(json.dumps(traced,indent=2)+'\n')
after={str(p):sha(p) for p in drivers};assert before==after
sources=[root/'tools/video_engine_probe.mm',root/'tools/video_loader_probe.mm',root/'tools/vda_engine_probe.mm',root/'src/trace_iokit.c',Path(__file__).resolve()]
sourceSnapshot=out/'source-snapshot';sourceSnapshot.mkdir(exist_ok=True)
for p in sources:(sourceSnapshot/p.name).write_bytes(p.read_bytes())
runtime=out/'runtime-snapshot';runtime.mkdir(exist_ok=True)
for name in ('video_engine_probe','video_loader_probe','vda_engine_probe','libTraceIOKit.dylib'):(runtime/name).write_bytes((root/'build'/name).read_bytes())
fixtures=[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in sorted(out.glob('*/fixture/*')) if p.is_file()]
manifest={'collected_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'driver_before_sha256':before,'driver_after_sha256':after,'drivers_unchanged':True,'cases':cases,'VDA_cases':vdaCases,'loader':loader,'PCI_display_inventory':displays,'fixtures':fixtures,
          'source_snapshot':[{'path':str((sourceSnapshot/p.name).relative_to(root)),'sha256':sha(p)} for p in sources],
          'runtime_snapshot':[{'path':str(p.relative_to(root)),'sha256':sha(p)} for p in sorted(runtime.iterdir()) if p.is_file()],
          'scope':'public H264 hardware-only sessions with CPU-encoded valid stream and software decoder controls; isolated process preload/registration variants; no raw vendor calls or performance benchmark'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Video probes:',len(cases),'CPU controls valid; hardware outcome recorded separately')
