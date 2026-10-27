#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck triple-context raster evidence and same-runtime regressions."""
import argparse
from datetime import datetime
import itertools
import json
from pathlib import Path
import subprocess
import sys

MODES=('gpu','native','no_dispatch','no_dispatch_native','vertex_only','vertex_only_native','pipeline_only','pipeline_only_native','pipeline_first','pipeline_first_native','draw_first','draw_first_native','reset','reset_native','foreign_vertex','foreign_vertex_native','foreign_index','foreign_index_native','reverse','reverse_native')
PILOT_FIRST={'pipeline_only','pipeline_only_native','vertex_only','vertex_only_native','pipeline_first','draw_first','reset','foreign_vertex','foreign_index'}
REGRESSIONS=(('regression-pipeline',('gpu','native','contracts','reverse'),'verify_pipeline_binding_integrated'),
             ('regression-combined',('gpu','native','foreign_vertex','missing_index'),'verify_combined_index_vertex'))


def audit(root):
 root=Path(root);runs=[];integrated={};regressions={};headers={};compute={};entries=[];libraries=set();refusals=0
 def run_name(mode,cohort):
  if cohort==1 and mode in PILOT_FIRST:return f'pilot2-{mode}'
  if cohort==1 and mode=='contracts':return 'cohort-contracts-01'
  return f'final-{mode}-{cohort:02}'
 for cohort in (1,2):
  for mode in MODES:runs.append((run_name(mode,cohort),'verify_triple_render',integrated,(cohort,mode)))
  runs.append((run_name('contracts',cohort),'verify_triple_render',integrated,(cohort,'contracts')))
 for prefix,modes,module in REGRESSIONS:
  for mode in modes:runs.append((f'{prefix}-{mode}',module,regressions,(prefix,mode)))
 for mode in ('bad_index_header','bad_index_header_native','bad_vertex_header','bad_vertex_header_native','bad_pipeline_header','bad_pipeline_header_native'):
  runs.append((f'header-{mode}','verify_triple_render',headers,mode))
 for mode in ('basic','stale_root'):runs.append((f'regression-compute-{mode}','verify_command_ir_dataflow',compute,mode))
 for name,module,group,key in runs:
  path=root/name;code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
  result=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True)
  proof=json.loads(result.stdout);assert proof['status']=='PASS';group[key]=proof
  if module=='verify_triple_render':refusals+=len(json.loads((path/'results.json').read_text()).get('refusals',[]))
  libraries.add(json.loads((path/'inputs.json').read_text())['static_library_SHA256'])
  receipt=json.loads((path/'execution/manifest.json').read_text());start=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at']);assert start<=end
  entries.append((start,end,receipt['pid'],name))
 entries.sort()
 for a,b in zip(entries,entries[1:]):assert a[1]<=b[0],(a,b)
 assert len({x[2]for x in entries})==len(entries) and len(libraries)==1
 image=lambda mode,c:(root/run_name(mode,c)/'outputs/image.bin').read_bytes()
 for cohort in (1,2):
  for mode in MODES:
   if not mode.endswith('native'):assert image(mode,cohort)==image(mode+'_native' if mode!='gpu' else 'native',cohort),(cohort,mode)
  assert image('gpu',cohort)==image('pipeline_first',cohort)==image('draw_first',cohort)
  assert image('gpu',cohort)==image('contracts',cohort)
  assert image('reverse',cohort)==image('no_dispatch',cohort)
  assert image('reset',cohort)==image('foreign_vertex',cohort)==image('foreign_index',cohort)
  signals=[image(mode,cohort) for mode in ('gpu','vertex_only','pipeline_only','no_dispatch')]
  assert all(a!=b for a,b in itertools.combinations(signals,2))
 for mode in MODES+('contracts',):assert image(mode,1)==image(mode,2),mode
 for mode in ('bad_index_header','bad_vertex_header','bad_pipeline_header'):
  assert (root/f'header-{mode}/outputs/image.bin').read_bytes()==(root/f'header-{mode}_native/outputs/image.bin').read_bytes()==image('reset',1)
 for prefix,_,_ in REGRESSIONS:assert (root/f'{prefix}-gpu/outputs/image.bin').read_bytes()==(root/f'{prefix}-native/outputs/image.bin').read_bytes()
 return {'status':'PASS','triple_hosts':len(integrated),'header_control_hosts':len(headers),'regression_hosts':len(regressions),'compute_regression_hosts':len(compute),'serialized_hosts':len(entries),
         'triple_float_channels':sum(x['checked_float_channels'] for x in integrated.values()),
         'triple_dispatches':sum(x['producer_dispatches'] for x in integrated.values()),
         'index_rows_checked':sum(x['index_rows_checked'] for x in integrated.values()),
         'vertex_rows_checked':sum(x['vertex_rows_checked'] for x in integrated.values()),
         'pipeline_rows_checked':sum(x['pipeline_rows_checked'] for x in integrated.values()),
         'regression_float_channels':sum(x['checked_float_channels'] for x in regressions.values()),
         'header_control_float_channels':sum(x['checked_float_channels'] for x in headers.values()),
         'compute_exact_uint32_results':sum(x['exact_uint32_results'] for x in compute.values()),
         'native_pairs':23,'repeat_image_pairs':21,'expected_api_refusals':refusals,'selector_combinations_distinct':True,
         'maximum_cpu_error':max(x['maximum_error'] for x in integrated.values()),
         'runtime_sha256':next(iter(libraries)),'scope':'scoped adapted client; not transparent Metal support'}


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
