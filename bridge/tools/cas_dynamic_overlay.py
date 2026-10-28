#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create a fresh CAS SDK overlay with one explicitly documented source variant."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE_NOISE='5bd7cfde71a0d4b7cde1679c156d61e5cac176a8d6fdbcd2374536ae0a97c5db'
def sha(data):return hashlib.sha256(data).hexdigest()
def need(v,reason):
 if not v:raise ValueError(reason)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lab-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();lab=a.lab_root.resolve();out=a.out.resolve()
 need(not out.exists(),'fresh overlay required')
 source=ROOT/'experiments/cas_dynamic_slot/dynamic_neighbor.metal';new=source.read_bytes();old=(lab/'results/native-cas-variants-captured/live_noise/test.metal').read_bytes()
 need(sha(old)==BASE_NOISE,'original live_noise source changed')
 need(b'shared[4]' in new and b'&shared[slot]' in new,'dynamic source invalid')
 cmd=[sys.executable,str(ROOT/'tools/cas_sdk_source_overlay.py'),'--lab-root',str(lab),'--out',str(out)]
 run=subprocess.run(cmd,capture_output=True,text=True,timeout=120);need(run.returncode==0,'base overlay failed: '+run.stderr[-2000:])
 inputs_path=out/'inputs.json';inputs=json.loads(inputs_path.read_text());fixtures=out/'results/native-cas-variants-captured/fixtures.json';original=fixtures.read_bytes();rows=json.loads(original)
 slot=[r for r in rows if r['name']=='live_noise'];need(len(slot)==1 and slot[0]['hashes']['test.metal']==BASE_NOISE,'live_noise manifest differs')
 target=out/'results/native-cas-variants-captured/live_noise/test.metal';need(sha(target.read_bytes())==BASE_NOISE,'copied live_noise differs')
 record=out/'results/dynamic-source-variant';record.mkdir();(record/'original-fixtures.json').write_bytes(original);(record/'dynamic.metal').write_bytes(new)
 # Do not leave historical compiled artifact hashes attached to the new source.
 slot[0]['hashes']={'test.metal':sha(new)};slot[0]['directory']=str(target.parent);slot[0]['source_variant']='explicit dynamic neighbor-guard source; no historical compiled artifacts'
 target.write_bytes(new);fixtures.write_text(json.dumps(rows,indent=2)+'\n')
 inputs['source_SHA256']['results/native-cas-variants-captured/live_noise/test.metal']=sha(new)
 inputs['source_SHA256']['results/native-cas-variants-captured/fixtures.json']=sha(fixtures.read_bytes())
 inputs['source_SHA256']['results/dynamic-source-variant/dynamic.metal']=sha(new)
 inputs['source_SHA256']['results/dynamic-source-variant/original-fixtures.json']=sha(original)
 inputs['derived_variant']={'source':'bridge/experiments/cas_dynamic_slot/dynamic_neighbor.metal','source_SHA256':sha(new),'replaced_fixture':'live_noise','previous_source_SHA256':BASE_NOISE,'previous_manifest_SHA256':sha(original),'kernel_function':'sdk_cas_noise','physical_address_expected':'register-indexed','GPU_qualification_pending':True}
 inputs_path.write_text(json.dumps(inputs,indent=2,sort_keys=True)+'\n')
 print(json.dumps({'status':'PASS','dynamic_source_SHA256':sha(new),'previous_source_SHA256':BASE_NOISE,'GPU_dispatch':False}))
if __name__=='__main__':main()
