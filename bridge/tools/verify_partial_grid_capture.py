#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check pinned compiler-container capture and repeat offline SM30 disassembly."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from partial_grid_capture import extract,PINS

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];f=i['function']
    assert f in PINS and r==read(p/'execution/execution.stdout') and r['pipeline_created'] and not r['gpu_dispatch'] and r['device']=='NVIDIA GeForce GTX 880M'
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert m['arguments']==[str(p/'assets'/PINS[f][0]),str(p/'capture'),'compute',f]
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256'] and sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    assert sha(p/'envydis')==i['envydis_SHA256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert sha(p/'assets'/PINS[f][0])==PINS[f][1] and m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    assert len(r['captures'])==1;cap=r['captures'][0];assert cap['class']=='NVMTLFunctionVariant' and cap['saved'] and cap['variant_saved'] and cap['read_status']==0
    assert cap['file']==str(p/'capture/program-0.compiler-output.bin') and cap['variant_file']==str(p/'capture/program-0.variant.bin')
    source=(p/'capture/program-0.compiler-output.bin').read_bytes();code=extract(source);assert len(source)==cap['input_bytes'] and code==(p/'capture/native.sass').read_bytes()
    assert read(p/'disassembly-execution.json')=={'exit_code':0,'GPU_dispatch':False}
    decoder=subprocess.run([str(p/'envydis'),'-m','gf100','-V','gk104','-i','-n',str(p/'capture/native.sass')],capture_output=True,text=True,timeout=30)
    listing=(p/'disassembly.stdout').read_text();assert decoder.returncode==0 and decoder.stdout==listing and decoder.stderr==(p/'disassembly.stderr').read_text()
    return {'verification':'PASS','function':f,'compiler_output_SHA256':sha(p/'capture/program-0.compiler-output.bin'),'code_SHA256':sha(p/'capture/native.sass'),
            'listing_SHA256':sha(p/'disassembly.stdout'),'code_bytes':len(code),'unknown_annotations':listing.count('[unknown'),
            'global_origin_710_refs':len(re.findall(r'c1\[0x710\]',listing)),
            'global_origin_714_refs':len(re.findall(r'c1\[0x714\]',listing)),
            'global_origin_718_refs':len(re.findall(r'c1\[0x718\]',listing)),
            'physical_cta_x_refs':len(re.findall(r'\$ctaidx\b',listing)),
            'physical_cta_y_refs':len(re.findall(r'\$ctaidy\b',listing)),
            'physical_cta_z_refs':len(re.findall(r'\$ctaidz\b',listing)),
            'GPU_execution_proved':False,'loaded_driver_memory_code_proved':False,'scalar_or_payload_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
