#!/usr/bin/env python3
"""Execute one IR-data cohort with the shared iMac GPU reservation."""
from pathlib import Path
import argparse,hashlib,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['producer','carrier','no_producer'],required=True);p.add_argument('--semantic',choices=['basic','barrier','clear','threads','copy'],default='basic');a=p.parse_args()
build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results')
inp=json.loads((build/'inputs.json').read_text())
for path,h in inp['files_SHA256'].items():assert sha(build/path)==h,path
out.mkdir(exist_ok=False);(out/'outputs').mkdir()
sys.path.insert(0,str(build/'runtime'));from run_sdk_host import run_host
m=run_host(build/'application',out/'execution',[str(build),str(out/'outputs'),a.mode,a.semantic],ROOT)
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n')
(out/'source-reference.json').write_text(json.dumps({'inputs_SHA256':sha(build/'inputs.json'),'compiler_manifest_SHA256':inp['compiler_manifest_SHA256'],'mode':a.mode,'semantic':a.semantic},indent=2)+'\n')
print(json.dumps({'mode':a.mode,'PID':m['pid'],'exit_code':m['exit_code'],'runs':len(d.get('runs',[])),'passed':d.get('passed')}))
