#!/usr/bin/env python3
"""Freeze identical MSL with a documented native Apple-device host adaptation."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--adapt-local-limit',action='store_true');a=p.parse_args()
    build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    inputs=json.loads((build/'inputs.json').read_text())
    assert sha(build/'control_flow.metal')==inputs['source_hashes']['control_flow.metal']
    shutil.copyfile(build/'control_flow.metal',out/'control_flow.metal')
    original=ROOT/'tools/control_flow_probe.mm';text=original.read_text()
    device='for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458&&[x.name isEqual:@"NVIDIA GeForce GTX 880M"])d=x;'
    driver='NSData*driver=[NSData dataWithContentsOfFile:@"/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver"];'
    guard='if(!d||![sha(driver)isEqual:@"2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"])return 2;'
    for before,after in [(device,'d=MTLCreateSystemDefaultDevice();'),(driver,'NSData*driver=[NSData data];'),(guard,'if(!d||![d.name containsString:@"M1 Max"])return 2;')]:
        assert text.count(before)==1;text=text.replace(before,after)
    assert text.count('@"device":d.name')==1
    text=text.replace('@"device":d.name','@"reference_target":@"Apple M1 Max",@"device":d.name')
    if a.adapt_local_limit:
        text=text.replace('locals[trial]','local')
        anchor='for(unsigned trial=0;trial<12;trial++){@autoreleasepool{';assert text.count(anchor)==1
        text=text.replace(anchor,anchor+'\n const unsigned requestedLocal=locals[trial],local=requestedLocal<=pso.maxTotalThreadsPerThreadgroup?requestedLocal:1;')
        assert text.count('@"local":@(local)')==1
        text=text.replace('@"local":@(local)','@"requested_local":@(requestedLocal),@"local":@(local)')
    (out/'control_flow_reference.mm').write_text(text)
    for name,source in [('run_control_flow_reference.py',ROOT/'tools/run_control_flow_reference.py'),('run_sdk_host.py',ROOT/'sdk-combined/runtime/run_sdk_host.py'),('lab_gpu_reservation.py',ROOT/'tools/lab_gpu_reservation.py')]:shutil.copyfile(source,out/name)
    changes=['Select default native Apple M1 Max device','Skip NVIDIA driver hash check; empty driver digest is not a vendor pin','Add reference_target result field']
    if a.adapt_local_limit:changes.append('Only when requested local exceeds the native PSO limit, use local1; total invocations/input bytes unchanged, requested/actual group shapes recorded')
    (out/'ADAPTATION.json').write_text(json.dumps({'original_host_SHA256':sha(original),'reference_host_SHA256':sha(out/'control_flow_reference.mm'),'MSL_SHA256':sha(out/'control_flow.metal'),'changes':changes,'unchanged':'MSL, buffer layouts, inputs, output and native pipeline calls; no NAK import compiled','source_build_inputs_SHA256':sha(build/'inputs.json'),'adapt_local_limit':a.adapt_local_limit},indent=2)+'\n')
    (out/'FILE_MANIFEST.json').write_text(json.dumps({'files':[{'path':f.name,'SHA256':sha(f)}for f in sorted(out.iterdir())]},indent=2)+'\n')
    print(json.dumps({'status':'PASS','MSL_SHA256':sha(out/'control_flow.metal'),'files':len(list(out.iterdir()))}))
if __name__=='__main__':main()
