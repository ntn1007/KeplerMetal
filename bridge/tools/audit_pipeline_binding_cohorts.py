#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck serialized GPU results and causal render pairs without GPU access."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import struct
import subprocess
import sys

RENDER = ('gpu','native','no_dispatch','no_dispatch_native','foreign','foreign_native',
          'reverse','reverse_native','reverse_no_dispatch','reverse_no_dispatch_native')
COMPUTE = ('active','wrong_token','foreign_source','wrong_slot','row_reserved',
           'bad_extension','bad_header','no_dispatch')


def audit(root):
    root=Path(root);entries=[];render={};compute={}
    for prefix,modes,module,results in (('pipeline-render',RENDER,'verify_pipeline_binding_render',render),
                                        ('pipeline-compute',COMPUTE,'verify_pipeline_binding_compute',compute)):
        for cohort in (1,2):
            for mode in modes:
                path=root/f'{prefix}-{mode}-{cohort:02}'
                code=('import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))')
                p=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True)
                proof=json.loads(p.stdout);results[(cohort,mode)]=proof
                receipt=json.loads((path/'execution/manifest.json').read_text())
                start=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at'])
                assert start<=end
                entries.append((start,end,receipt['pid'],prefix,mode))
    entries.sort()
    for first,second in zip(entries,entries[1:]):assert first[1]<=second[0],(first,second)
    assert len({x[2] for x in entries})==len(entries)
    pairs=(('gpu','native'),('no_dispatch','no_dispatch_native'),('foreign','foreign_native'),
           ('reverse','reverse_native'),('reverse_no_dispatch','reverse_no_dispatch_native'))
    for cohort in (1,2):
        for a,b in pairs:
            assert (root/f'pipeline-render-{a}-{cohort:02}/outputs/image.bin').read_bytes()==(root/f'pipeline-render-{b}-{cohort:02}/outputs/image.bin').read_bytes(),(cohort,a,b)
    for mode in RENDER:
        assert (root/f'pipeline-render-{mode}-01/outputs/image.bin').read_bytes()==(root/f'pipeline-render-{mode}-02/outputs/image.bin').read_bytes(),mode
    active=(root/'pipeline-render-gpu-01/outputs/image.bin').read_bytes()
    unchanged=(root/'pipeline-render-no_dispatch-01/outputs/image.bin').read_bytes()
    foreign=(root/'pipeline-render-foreign-01/outputs/image.bin').read_bytes()
    assert active!=unchanged and active!=foreign and unchanged!=foreign
    def different_channels(a,b):
        x=struct.unpack('<12288f',a[256:-256]);y=struct.unpack('<12288f',b[256:-256])
        return sum(u!=v for u,v in zip(x,y))
    return {'status':'PASS','render_hosts':len(render),'compute_hosts':len(compute),
            'render_float_channels':sum(x['checked_float_channels'] for x in render.values()),
            'render_dispatches':sum(x['dispatches'] for x in render.values()),
            'compute_dispatches':sum(x['dispatches'] for x in compute.values()),
            'render_native_pairs':len(pairs)*2,'repeat_image_pairs':len(RENDER),
            'unique_serialized_hosts':len(entries),'causal_images_distinct':True,
            'active_vs_no_dispatch_different_channels':different_channels(active,unchanged),
            'active_vs_foreign_different_channels':different_channels(active,foreign),
            'maximum_cpu_error':max(x['maximum_error'] for x in render.values()),
            'scope':'explicit laboratory context; not native Apple ICB ABI or transparent application support'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
