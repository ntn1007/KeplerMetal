#!/usr/bin/env python3
"""Read-only system inventory. All output is confined to this research directory."""
import datetime, hashlib, json, pathlib, plistlib, subprocess
ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'inventory'
OUT.mkdir(parents=True, exist_ok=True)
def command(args, name, timeout=45):
    p = subprocess.run(args, capture_output=True, timeout=timeout)
    (OUT / name).write_bytes(p.stdout)
    (OUT / (name + '.stderr')).write_bytes(p.stderr)
    return {'argv': args, 'exit_code': p.returncode, 'stdout_file': name}
commands = []
for args, name in [
    (['/usr/bin/sw_vers'], 'sw_vers.txt'),
    (['/usr/sbin/sysctl','hw.model','hw.memsize','hw.physicalcpu','hw.logicalcpu','machdep.cpu.brand_string','machdep.cpu.features','machdep.cpu.leaf7_features'], 'hardware.txt'),
    (['/usr/bin/uname','-a'], 'uname.txt'),
    (['/usr/bin/kmutil','showloaded'], 'loaded-kexts.txt'),
    (['/bin/df','-h',str(ROOT)], 'disk.txt'),
]:
    commands.append(command(args, name))
p = subprocess.run(['/usr/sbin/system_profiler','SPDisplaysDataType','-json'],capture_output=True,timeout=45)
displays = json.loads(p.stdout)
keep = ['_name','sppci_model','spdisplays_device-id','spdisplays_vendor','spdisplays_revision-id','spdisplays_vram','spdisplays_pcie_width','spdisplays_rom-revision','spdisplays_metal','spdisplays_bus']
gpu = [{k:v for k,v in d.items() if k in keep} for d in displays['SPDisplaysDataType']]
(OUT/'gpu.json').write_text(json.dumps(gpu,indent=2)+'\n')
commands.append({'argv':['/usr/sbin/system_profiler','SPDisplaysDataType','-json'],'exit_code':p.returncode,'stdout_file':'gpu.json','redaction':'display EDID, serial numbers, and display IDs omitted'})
patch_path=pathlib.Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')
patch=plistlib.loads(patch_path.read_bytes())
(OUT/'oclp-root-patches.json').write_text(json.dumps(patch,indent=2,default=str)+'\n')
components=[]
names=['GeForce.kext','GeForceAIRPlugin.bundle','GeForceGLDriver.bundle','GeForceMTLDriver.bundle','GeForceVADriver.bundle','NVDAGF100Hal.kext','NVDAGK100Hal.kext','NVDAResman.kext','NVDAStartup.kext','IOAcceleratorFamily2.kext']
paths=[pathlib.Path('/System/Library/Extensions')/n for n in names]
paths += [pathlib.Path('/System/Library/Frameworks')/(n+'.framework') for n in ['Metal','OpenCL']]
paths += [pathlib.Path('/System/Library/PrivateFrameworks')/(n+'.framework') for n in ['GPUCompiler','MTLCompiler']]
paths += [p for p in pathlib.Path('/Applications').glob('*OpenCore*.app')]
for path in paths:
    infos=[path/'Contents/Info.plist',path/'Resources/Info.plist',path/'Versions/A/Resources/Info.plist']
    info_path=next((p for p in infos if p.exists()),None)
    if not info_path:
        components.append({'path':str(path),'info_found':False});continue
    info=plistlib.loads(info_path.read_bytes());exe_name=info.get('CFBundleExecutable')
    row={'path':str(path),'info_path':str(info_path),'identifier':info.get('CFBundleIdentifier'),'version':info.get('CFBundleVersion'),'short_version':info.get('CFBundleShortVersionString'),'info_sha256':hashlib.sha256(info_path.read_bytes()).hexdigest()}
    binaries=[path/'Contents/MacOS'/str(exe_name),path/str(exe_name),path/'Versions/A'/str(exe_name)] if exe_name else []
    binary=next((p for p in binaries if p.is_file()),None)
    if binary:
        row.update(executable=str(binary),bytes=binary.stat().st_size,sha256=hashlib.sha256(binary.read_bytes()).hexdigest())
    components.append(row)
(OUT/'components.json').write_text(json.dumps(components,indent=2)+'\n')
metadata={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'commands':commands,'root_patch_plist':str(patch_path),'root_patch_plist_sha256':hashlib.sha256(patch_path.read_bytes()).hexdigest(),'system_mutations':False,'scope':'System commands and file reads only; output written in workspace. No NVRAM, boot or system changes.'}
(OUT/'inventory-manifest.json').write_text(json.dumps(metadata,indent=2)+'\n')
print(json.dumps({'gpu':gpu,'components':components,'commands':commands},indent=2))
