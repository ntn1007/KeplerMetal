#!/usr/bin/env python3
"""Freeze the exact reception client for native MTLFunction-encoder reference."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--client-source',type=Path,default=ROOT/'tools/command_ir_dataflow_client.mm');p.add_argument('--factory-kind',type=int,choices=range(6),default=0);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
client=a.client_source.resolve();client.relative_to(ROOT)
for source,name in [
 (client,'command_ir_dataflow_client.mm'),
 (ROOT/'src/KeplerCPUICB.h','KeplerCPUICB.h'),
 (ROOT/'src/cpu_icb_dependency.metal','cpu_icb_dependency.metal'),
 (ROOT/'src/cpu_icb_dependency_manifest.json','cpu_icb_dependency_manifest.json'),
 (ROOT/'src/gpu_command_frontend_dataflow.metal','gpu_command_frontend_dataflow.metal'),
 (ROOT/'sdk-combined/runtime/run_sdk_host.py','run_sdk_host.py'),
 (ROOT/'tools/lab_gpu_reservation.py','lab_gpu_reservation.py'),
 (ROOT/'tools/PublicArgumentRefusals.inc','PublicArgumentRefusals.inc')]:shutil.copyfile(source,out/name)
s=(ROOT/'tools/run_m1_command_ir_dataflow.py').read_text();anchor="'-DKP_DATAFLOW_NATIVE=1',";assert s.count(anchor)==1
s=s.replace(anchor,anchor+"'-DKP_PUBLIC_ARGUMENT_ENCODER=1','-DKP_FUNCTION_ARGUMENT_ENCODER=1',",1)
if a.factory_kind:
 anchor="str(out/'assets'),str(target/'outputs'),mode";assert s.count(anchor)==1;s=s.replace(anchor,"str(out/'assets'),str(target/'outputs'),str("+str(a.factory_kind)+")+':'+mode",1)
helper=client.parent/'PipelineFactoryReception.inc'
if helper.exists():shutil.copyfile(helper,out/helper.name)
(out/'run_m1_command_ir_dataflow.py').write_text(s)
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
(out/'FILE_MANIFEST.json').write_text(json.dumps({'files':[{'path':f.name,'bytes':f.stat().st_size,'SHA256':sha(f)}for f in sorted(out.iterdir())],'GPU_execution':False,'function_argument_encoder':True,'Qwen_job_ids':[]},indent=2)+'\n')
print(json.dumps({'status':'PASS','source':str(out),'client_SHA256':sha(out/'command_ir_dataflow_client.mm')}))
