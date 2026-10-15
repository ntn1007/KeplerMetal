#!/usr/bin/env python3
"""Independently decode generated SM30 files; never open a GPU device."""
from pathlib import Path
import json
import subprocess
import hashlib

root = Path(__file__).resolve().parents[1]
decoder = root/'build/envydis-only/envydis/envydis'
results = []
for extension in ('air','metallib'):
    binary = root/('build/add_buffers-'+extension+'.sass')
    output = root/('results/add_buffers-'+extension+'.envydis.txt')
    command = [str(decoder),'-m','gf100','-V','gk104','-i','-n',str(binary)]
    with output.open('w') as out,(root/('logs/disassemble-'+extension+'.log')).open('w') as err:
        result = subprocess.run(command,stdout=out,stderr=err)
    listing = output.read_text()
    data = binary.read_bytes()
    results.append({'input':str(binary),'command':command,'exit_code':result.returncode,
                    'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                    'unknown_instruction_count':listing.count('[unknown instruction]'),
                    'unknown_operand_count':listing.count('[unknown operand]'),
                    'unknown_bit_annotation_count':listing.count('[unknown:'),
                    'gpu_execution_tested':False})
    if result.returncode: raise SystemExit(result.returncode)
summary = {'architecture':'GK104/SM30', 'decoder':'envytools gf100 ISA, gk104 variant',
           'files':results,'identical_machine_code':results[0]['sha256']==results[1]['sha256'],
           'scope':'offline ISA decoding; does not establish numerical correctness on GPU'}
(root/'results/disassembly-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
