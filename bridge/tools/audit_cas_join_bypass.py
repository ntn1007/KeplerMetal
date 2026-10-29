#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check offline reconvergence-bypass counterexamples; never submit them to a GPU."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from recognize_native_cas import recognize, verify_decoder

PREVIOUS = '1b5bcd072a94021b0eee966b67d0fcc9763462abdd1e2f2a311bab4a15e259e7'
ASSEMBLER = '1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e'


def sha(data): return hashlib.sha256(data).hexdigest()
def need(ok, message):
    if not ok: raise ValueError(message)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'cases', 'assembler', 'decoder', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    need(sha(a.previous.read_bytes()) == PREVIOUS and sha(a.assembler.read_bytes()) == ASSEMBLER, 'tool identity')
    spec = importlib.util.spec_from_file_location('old_cas_join_bypass', a.previous)
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    archived = []
    for name, expected in [('slot1', True), ('permuted', True), ('live_noise', True), ('original_compare_control', False)]:
        before = old.recognize(a.cases/name, a.decoder); after = recognize(a.cases/name, a.decoder)
        need(before['qualified'] == after['qualified'] == expected and before['decoder_reproduced_listing'] and
             after['decoder_reproduced_listing'], 'archived verdict: '+name)
        archived.append({'name': name, 'qualified': expected, 'native_sha256': after['hashes']['native.sass']})
    source = (a.cases/'slot1/native.sass').read_bytes()
    need(verify_decoder(source, (a.cases/'slot1/native.asm').read_text(), a.decoder), 'original decoder mismatch')
    cases = [('next_instruction', 'joinat 0x2f8'), ('schedule_word', 'joinat 0x300'),
             ('output_store', 'joinat 0x328')]
    variants = []
    with tempfile.TemporaryDirectory(prefix='kepler-cas-join-bypass-') as temp:
        root = Path(temp)
        for name in ('test.metal', 'test.air', 'test.metallib', 'typed-air.json'):
            shutil.copyfile(a.cases/'slot1'/name, root/name)
        for name, operation in cases:
            offset = 0x2a0; assembly = root/(name+'.easm'); binary = root/(name+'.bin')
            assembly.write_text('.section #code 0;\n.skip 0x2a0;\nlong '+operation+';\n')
            run = subprocess.run([str(a.assembler), '-m', 'gf100', '-V', 'gk104', '-i', '-o', str(binary),
                                  str(assembly)], capture_output=True, timeout=20)
            need(run.returncode == 0 and len(binary.read_bytes()) >= offset+8, 'assembly: '+name)
            modified = bytearray(source); modified[offset:offset+8] = binary.read_bytes()[offset:offset+8]
            code = bytes(modified)
            need([i for i in range(0, len(source), 8) if source[i:i+8] != code[i:i+8]] == [offset], 'mutation: '+name)
            (root/'native.sass').write_bytes(code)
            dec = subprocess.run([str(a.decoder), '-m', 'gf100', '-V', 'gk104', '-i', '-n', str(root/'native.sass')],
                                 capture_output=True, timeout=20)
            text = dec.stdout.decode('utf-8')
            need(dec.returncode == 0 and verify_decoder(code, text, a.decoder) and
                 any(line.startswith('000002a0:') and line.endswith(operation) for line in text.splitlines()), 'decoder: '+name)
            (root/'native.asm').write_text(text)
            before = old.recognize(root, a.decoder); after = recognize(root, a.decoder)
            need(before['qualified'] and before['AIR']['qualified'] and before['decoder_reproduced_listing'] and
                 not after['qualified'] and after['AIR']['qualified'] and after['decoder_reproduced_listing'], 'verdict: '+name)
            variants.append({'name': name, 'offset': '0x2a0', 'operation': operation,
                             'synthetic_program_sha256': sha(code), 'listing_sha256': sha(dec.stdout),
                             'previous_qualified': True, 'updated_qualified': False})
    result = {'status': 'PASS_OFFLINE_RECONVERGENCE_BYPASS_GUARD', 'previous_recognizer_sha256': PREVIOUS,
              'current_recognizer_sha256': sha(Path(recognize.__code__.co_filename).read_bytes()),
              'assembler_sha256': sha(a.assembler.read_bytes()), 'decoder_sha256': sha(a.decoder.read_bytes()),
              'original_program_sha256': sha(source), 'counterexamples': variants, 'archived_cases': archived,
              'synthetic_air_sass_compiler_correspondence_proved': False, 'decoder_semantics_proved': False,
              'gpu_dispatches': 0, 'system_modified': False}
    with a.out.open('x') as out: json.dump(result, out, indent=2, sort_keys=True); out.write('\n')
    print(json.dumps({'status': result['status'], 'counterexamples': len(variants), 'archived_cases': len(archived)}))


if __name__ == '__main__': main()
