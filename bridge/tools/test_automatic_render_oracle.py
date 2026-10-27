#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline mutation checks on copies of two completed automatic-render runs."""
import argparse,json,shutil,struct,sys,tempfile
from pathlib import Path

def test(root):
 root=Path(root).resolve();assert (root/'accepted-auto-01').is_dir() and (root/'accepted-unsupported-01').is_dir();out=[]
 with tempfile.TemporaryDirectory(prefix='kepler-oracle-') as temporary:
  base=Path(temporary)
  for mode in ('auto','unsupported'):
   source=root/f'accepted-{mode}-01';copy=base/mode;shutil.copytree(source,copy)
   mpath=copy/'execution/manifest.json';m=json.loads(mpath.read_text());m['arguments']=[str(copy/'assets'),str(copy/'assets/client.dylib'),str(copy/'outputs'),mode];mpath.write_text(json.dumps(m))
   sys.path.insert(0,str(copy/'oracles'));from verify_automatic_render import verify
   assert verify(copy)['status']=='PASS'
   def rejected(name,change,undo):
    change()
    try:verify(copy)
    except (AssertionError,KeyError,ValueError):out.append(name)
    else:raise AssertionError('Mutation was not detected: '+name)
    finally:undo()
   image=copy/'outputs/frame-0.bin';original=image.read_bytes()
   rejected(mode+'-pixels',lambda:image.write_bytes(original[:256]+struct.pack('<f',0.0)+original[260:]),lambda:image.write_bytes(original))
   dylib=copy/'assets/client.dylib';binary=dylib.read_bytes()
   rejected(mode+'-client-hash',lambda:dylib.write_bytes(binary[:-1]+bytes([binary[-1]^1])),lambda:dylib.write_bytes(binary))
   result=copy/'results.json';stdout=copy/'execution/execution.stdout';data=json.loads(result.read_text());rbytes=result.read_bytes();sbytes=stdout.read_bytes()
   def modify(field):
    v=json.loads(rbytes);field(v);serialized=json.dumps(v);result.write_text(serialized);stdout.write_text(serialized)
   def restore():result.write_bytes(rbytes);stdout.write_bytes(sbytes)
   if mode=='auto':
    rejected('encoder-class',lambda:modify(lambda x:x['client']['render_encoder_classes'].__setitem__(0,'NVMTLRenderCommandEncoder_KEPLER_A')),restore)
    rejected('shared-methods',lambda:modify(lambda x:x.__setitem__('shared_native_classes_replaced',True)),restore)
   else:rejected('guard-reason',lambda:modify(lambda x:x['client']['unsupported_exceptions'][0].__setitem__('reason','unrelated exception')),restore)
   assert verify(copy)['status']=='PASS';sys.path.pop(0)
 return {'status':'PASS','positive_copied_runs':2,'rejected_mutations':out,'GPU_execution':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args();assert not a.out.exists();a.out.write_text(json.dumps(test(a.root),indent=2)+'\n');print(a.out)
