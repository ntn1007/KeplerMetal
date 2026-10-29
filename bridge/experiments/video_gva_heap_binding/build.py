#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare the calibrated heap observer and existing request witness."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent
HEAP=HERE.parent/'video_gva_heap_watch'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,msg):
    if not x:raise ValueError(msg)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('lab','parent','heap-calibration','out'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();lab,parent,cal,out=(getattr(a,n).resolve() for n in ('lab','parent','heap_calibration','out'))
    for path in (parent,cal,out):path.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    b=json.loads((parent/'build.json').read_text());c=json.loads((cal/'calibration.json').read_text())
    need(b['request_window_variant'] and c['status']=='PASS_TWO_CPU_CROSS_IMAGE_CONTROLS' and
         c['positive_free_and_zone_free_per_process'] and c['unrelated_pointer_excluded'],'qualification differs')
    for n,h in b['frozen'].items():need(sha(parent/n)==h,'parent differs: '+n)
    for n,h in c['sources_sha256'].items():
        source=(HEAP.parent/'video_gva_repeat_sessions'/n) if n=='repeat_gate.h' else HEAP/n
        need(sha(cal/n)==sha(source)==h,'heap source differs')
    need(sha(cal/'heap-watch.dylib')==c['observer_sha256'],'heap binary differs')
    out.mkdir()
    for n in b['frozen']:shutil.copyfile(parent/n,out/n)
    shutil.copyfile(cal/'heap-watch.dylib',out/'heap-watch.dylib')
    shutil.copyfile(HERE/'lldb_binding.py',out/'lldb_binding.py')
    frozen={n:sha(out/n) for n in (*b['frozen'],'heap-watch.dylib','lldb_binding.py')}
    data={**b,'frozen':frozen,'heap_binding_variant':True,'parent_build_sha256':sha(parent/'build.json'),
          'heap_calibration_sha256':sha(cal/'calibration.json'),'heap_observer_sha256':c['observer_sha256'],
          'binding_source_sha256':sha(HERE/'lldb_binding.py'),'builder_sha256':sha(Path(__file__)),
          'GPU_execution':False,'system_modified':False}
    (out/'build.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED_HEAP_BINDING_WITNESS','GPU_execution':False}))


if __name__=='__main__':main()
