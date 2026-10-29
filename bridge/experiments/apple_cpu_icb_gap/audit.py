#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit pinned Apple sample inputs and non-dispatch GTX reflection controls."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
 if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('sample','build','archive','out'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--runs',type=Path,nargs=2,required=True);a=p.parse_args();need(not a.out.exists() and len(set(a.runs))==2,'fresh output / distinct runs')
 sample=a.sample.resolve();source=sample/'source';need(sha(sample/'AppleSample.zip')=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive differs')
 pins={'Renderer/AAPLShaders.metal':'175efc7a343ddb1a98f9d3467bb9e73f7d5a42c3ad54ab5567240c732fe02976','Renderer/AAPLShaderTypes.h':'7f6b70576fb1e00422520f273530fd55e4fe5036c42b11bdf74205bae64609a2'}
 for n,h in pins.items():need(sha(source/n)==h,'Apple source differs')
 shader=(source/'Renderer/AAPLShaders.metal').read_text();types=(source/'Renderer/AAPLShaderTypes.h').read_text();renderer=(source/'Renderer/AAPLRenderer.m').read_text();controller=(source/'Application/AAPLViewController.m').read_text()
 need('#define AAPLNumObjects    15' in types and 'supportsFamily:MTLGPUFamilyMac2' in controller and 'icbDescriptor.maxVertexBufferBindCount = 3' in renderer and 'icbDescriptor.inheritPipelineState = YES' in renderer and 'vertexID' in shader and 'object_params[objectIndex]' in shader,'sample structure differs')
 log=(sample/'build.log').read_text();app=sample/'derived/Build/Products/Debug/Indirect Command Buffers on CPU.app/Contents/MacOS/Indirect Command Buffers on CPU';need('** BUILD SUCCEEDED **' in log and app.is_file() and 'CODE_SIGNING_ALLOWED=NO' in log,'sample build evidence')
 build=a.build.resolve();archive=a.archive.resolve();b=load(build/'build.json');ar=load(archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build/archive')
 for n,h in ar['source_SHA256'].items():need(sha(archive/'src'/n)==sha(BRIDGE/'src'/n)==h,'archive source differs')
 for n,h in b['files_sha256'].items():need(sha(build/n)==h,'build asset differs')
 need(sha(build/'client.mm')==sha(HERE/'client.mm') and sha(build/'vertex.metallib')==sha(sample/'apple.metallib') and sha(build/'profiles.json')==sha(sample/'apple-empty-stage-manifest.json'),'client/assets differ');sign(build/'application')
 intervals=[];rows=[];expected=[(0,'vertices',16,4),(1,'object_params',8,4),(2,'frame_state',8,256)]
 for path in a.runs:
  root=path.resolve();m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']=='direct' and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process evidence');sign(root/'application')
  need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log') and not list((root/'outputs').iterdir()),'logs/system/output')
  x=load(root/'stdout.json');args=sorted(x['vertex_arguments'],key=lambda v:v['index']);need(x['status']=='PASS' and x['device']=='NVIDIA GeForce GTX 880M' and x['mac1'] and not x['mac2'] and x['gpu_dispatches']==0 and x['registration_refused'] and x['descriptor_refused'] and x['registration_reason']=='Fragment resources or non-stage-in vertex ABI are not supported','client state');need([(v['index'],v['name'],v['buffer_data_size'],v['buffer_alignment']) for v in args]==expected and all(v['type']==0 and v['access']==0 and v['active'] for v in args),'reflection')
  intervals.append((m['started_at'],m['completed_at']));rows.append({'manifest_sha256':sha(root/'manifest.json'),'stdout_sha256':sha(root/'stdout.json')})
 intervals.sort();need(intervals[0][0]<=intervals[0][1]<=intervals[1][0]<=intervals[1][1],'process overlap')
 result={'status':'PASS_APPLE_SAMPLE_GAP_REFLECTION','apple_archive_sha256':sha(sample/'AppleSample.zip'),'apple_source_sha256':pins,'apple_build_log_sha256':sha(sample/'build.log'),'apple_app_sha256':sha(app),'apple_build_succeeded':True,'apple_app_executed':False,'apple_sample_object_count':15,'mac1_advertised':True,'mac2_advertised':False,'vertex_arguments':expected,'scoped_registration_refused':True,'scoped_three_buffer_descriptor_refused':True,'processes':2,'gpu_dispatches':0,'apple_sample_gpu_execution_proved':False,'full_icb_contract':False,'checked_system_files_unchanged':True,'runs':rows}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'gpu_dispatches':0,'reflected_buffers':3}))
if __name__=='__main__':main()
