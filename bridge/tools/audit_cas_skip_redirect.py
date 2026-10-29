#!/usr/bin/env python3
"""Offline branch counterexamples; never execute the mutated GPU program."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from recognize_native_cas import sass_contract, verify_decoder

PREVIOUS = 'bf9555f211ec49ff2b429cfcfba6ac23e63eebcd3af14e913bf540b37d9bf285'
ASSEMBLER = '1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e'

def sha(data): return hashlib.sha256(data).hexdigest()
def need(ok, reason):
    if not ok: raise ValueError(reason)

p = argparse.ArgumentParser(description=__doc__)
for field in ('previous', 'source', 'listing', 'assembler', 'decoder', 'out'):
    p.add_argument('--' + field, required=True, type=Path)
a = p.parse_args()
need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
need(sha(a.previous.read_bytes()) == PREVIOUS and sha(a.assembler.read_bytes()) == ASSEMBLER,
     'unapproved previous recognizer or assembler')
spec = importlib.util.spec_from_file_location('previous_cas_skip', a.previous)
old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
source = a.source.read_bytes(); listing = a.listing.read_text()
need(verify_decoder(source, listing, a.decoder), 'original decoder mismatch')
need(old.sass_contract(source, listing, 0)['qualified'] and sass_contract(source, listing, 0)['qualified'],
     'original structural verdict differs')
rows = []
with tempfile.TemporaryDirectory(prefix='kepler-cas-skip-') as directory:
    t = Path(directory)
    for name, operation in [('direct', 'bra 0x328'), ('positive', '$p1 bra 0x328'),
                            ('negative', '(not $p1) bra 0x328')]:
        offset = 0x2a0
        assembly, assembled = t / (name + '.easm'), t / (name + '.bin')
        assembly.write_text('.section #code 0;\n.skip %#x;\nlong %s;\n' % (offset, operation))
        run = subprocess.run([str(a.assembler), '-m', 'gf100', '-V', 'gk104', '-i',
                              '-o', str(assembled), str(assembly)], capture_output=True, timeout=20)
        need(run.returncode == 0 and len(assembled.read_bytes()) >= offset + 8, 'assembly failed: ' + name)
        data = bytearray(source); data[offset:offset+8] = assembled.read_bytes()[offset:offset+8]
        code = bytes(data)
        need([i for i in range(0, len(source), 8) if source[i:i+8] != code[i:i+8]] == [offset],
             'expected one changed word')
        binary = t / (name + '.sass'); binary.write_bytes(code)
        dec = subprocess.run([str(a.decoder), '-m', 'gf100', '-V', 'gk104', '-i', '-n', str(binary)],
                             capture_output=True, timeout=20)
        text = dec.stdout.decode('utf-8')
        need(dec.returncode == 0 and verify_decoder(code, text, a.decoder) and
             any(line.startswith('%08x:' % offset) and line.endswith(operation) for line in text.splitlines()),
             'decoder mismatch: ' + name)
        before, after = old.sass_contract(code, text, 0), sass_contract(code, text, 0)
        need(before['qualified'] and not after['qualified'], 'unexpected verdict: ' + name)
        rows.append({'name': name, 'offset': hex(offset), 'operation': operation,
                     'synthetic_sha256': sha(code), 'listing_sha256': sha(dec.stdout),
                     'previous_qualified': True, 'current_qualified': False})

result = {'status': 'PASS', 'source_sha256': sha(source), 'previous_sha256': PREVIOUS,
          'current_sha256': sha(Path(sass_contract.__code__.co_filename).read_bytes()),
          'assembler_sha256': ASSEMBLER, 'decoder_sha256': sha(a.decoder.read_bytes()),
          'rows': rows, 'air_sass_correspondence_proved': False, 'decoder_semantics_proved': False,
          'gpu_execution': False}
with a.out.open('x') as f: json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
print(json.dumps({'status': result['status'], 'counterexamples': len(rows)}))
