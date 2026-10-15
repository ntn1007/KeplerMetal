#!/usr/bin/env python3
from pathlib import Path
import argparse,json
from fp64_reverse_inputs import OPS,columns,expected_bits,equivalent_for
from verify_fp64_conversions import verify as common_verify

def verify(root,portable=False):
 op=json.loads((Path(root)/'plan.json').read_text())['shader_info']['operation']
 v=common_verify(root,portable,operators=OPS,recipe='fp64-reverse-v1',column_function=columns,result_function=expected_bits,compare_function=lambda observed,wanted:equivalent_for(op,observed,wanted))
 v['oracle']='Integer-only IEEE conversion/rounding, crosschecked with C fenv/Python Fraction'
 v['rounding_mode']=op[-2:];v['output_format']=op.split('_')[1];v['integer_specials']='Saturate out of range; NaN→0'
 return v

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k not in ('raw_SHA256','errors')},indent=2))
 raise SystemExit(0 if v['status'].startswith('PASS') else 1)
