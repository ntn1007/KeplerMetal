#!/usr/bin/env python3
"""Crosscheck bit reference with x86 C fenv conversion and Python integer maths."""
from pathlib import Path
import argparse,ctypes,hashlib,json,math,subprocess,struct
from fractions import Fraction
from fp64_reverse_inputs import OPS,columns,expected_bits,equivalent_for

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
source=out/'reference.c';source.write_text('''#include <stdint.h>
#include <string.h>
#include <fenv.h>
#pragma STDC FENV_ACCESS ON
uint32_t reference_f32(uint64_t raw, int mode) {
    fenv_t saved; fegetenv(&saved);
    int modes[4]={FE_TONEAREST,FE_TOWARDZERO,FE_UPWARD,FE_DOWNWARD};
    fesetround(modes[mode]);
    double input; memcpy(&input,&raw,8); volatile double value=input;
    volatile float converted=(float)value; float output=converted;
    uint32_t bits; memcpy(&bits,&output,4); fesetenv(&saved); return bits;
}
''')
library=out/'reference.dylib';argv=['clang','-arch','x86_64','-O0','-std=c11','-frounding-math','-dynamiclib',str(source),'-o',str(library)]
r=subprocess.run(argv,capture_output=True,text=True,timeout=30);(out/'compile.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr
lib=ctypes.CDLL(str(library));lib.reference_f32.argtypes=[ctypes.c_uint64,ctypes.c_int];lib.reference_f32.restype=ctypes.c_uint32
checks=0;per_op={}
for op in OPS:
 total=0
 for local,count in [(32,33),(128,1041),(1024,8193)]:
  for trial in range(3):
   for raw in columns(op,local,count,trial)[0]:
    mode=op[-2:];target=op.split('_')[1]
    if target=='f32':ref=lib.reference_f32(raw,['rn','rz','rp','rm'].index(mode))
    else:
     v=struct.unpack('<d',struct.pack('<Q',raw))[0];low=-(1<<63) if target=='i64' else 0;high=(1<<63)-1 if target=='i64' else (1<<64)-1
     if math.isnan(v):ref=0
     elif math.isinf(v):ref=(low if v<0 else high)&((1<<64)-1)
     else:
      exact=Fraction.from_float(v);integer={'rn':round,'rz':int,'rp':math.ceil,'rm':math.floor}[mode](exact);ref=min(max(integer,low),high)&((1<<64)-1)
    want=expected_bits(op,raw);assert equivalent_for(op,ref,want),(op,hex(raw),hex(ref),hex(want));checks+=1;total+=1
 per_op[op]=total
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
result={'status':'PASS','CPU_only':True,'checks':checks,'per_operation':per_op,'oracle_SHA256':sha(ROOT/'tools/fp64_reverse_inputs.py'),'C_source_SHA256':sha(source),'C_library_SHA256':sha(library),'GPU_execution':False}
(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
