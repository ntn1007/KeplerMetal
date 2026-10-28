#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline regression for a JOIN-modified register write; never dispatches GPU code."""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import tempfile
from pathlib import Path

import recognize_native_cas as current


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'generated', 'assembler', 'decoder', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists() and args.out.parent.is_dir(), 'fresh output required')
    spec = importlib.util.spec_from_file_location('previous_recognizer', args.previous)
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    names = ('sdk_cas_expected', 'sdk_cas_slot', 'sdk_cas_noise',
             'sdk_cas_swizzle', 'sdk_keep_comparand')
    regressions = []
    for name in names:
        directory = args.generated / ('diagnosis-' + name)
        state = json.loads((directory / 'diagnosis.json').read_text())
        module = json.loads((directory / 'typed-air.json').read_text())
        before_air = previous.air_contract(module, name)
        after_air = current.air_contract(module, name)
        require(before_air == after_air == state['AIR'], 'AIR mismatch: ' + name)
        if not after_air['qualified']:
            require(not state['candidate'], 'unexpected AIR refusal: ' + name)
            regressions.append({'function': name, 'candidate': False, 'stage': 'AIR'})
            continue
        code = (directory / 'native.sass').read_bytes()
        listing = (directory / 'native.asm').read_text()
        require(current.verify_decoder(code, listing, args.decoder), 'decoder mismatch: ' + name)
        before = previous.sass_contract(code, listing, after_air['expected_output_component'])
        after = current.sass_contract(code, listing, after_air['expected_output_component'])
        require(before == after == state['SASS'] and after['qualified'] == state['candidate'],
                'changed original diagnosis: ' + name)
        regressions.append({'function': name, 'candidate': state['candidate'],
                            'native_SHA256': digest(code)})

    directory = args.generated / 'diagnosis-sdk_cas_noise'
    original = (directory / 'native.sass').read_bytes()
    require(digest(original) == '7640c32a4ea4a078dd4e3bf149a15f1fef77e4e22a56018f3f5ed6fa2c6f541c',
            'original program profile differs')
    with tempfile.TemporaryDirectory(prefix='kepler-join-cas-offline-') as temp:
        temp = Path(temp)
        source, assembled, program = temp/'join.easm', temp/'join.bin', temp/'program.sass'
        source.write_text('.section #code 0;\n.skip 0x390;\nlong join mov b32 $r9 $r6;\n')
        assembly = subprocess.run([str(args.assembler), '-m', 'gf100', '-V', 'gk104', '-i',
                                   '-o', str(assembled), str(source)], capture_output=True, timeout=20)
        require(assembly.returncode == 0, 'offline assembly failed')
        words = assembled.read_bytes()
        require(len(words) >= 0x398, 'assembled instruction missing')
        modified = bytearray(original)
        modified[0x390:0x398] = words[0x390:0x398]
        code = bytes(modified)
        require([i for i in range(0, len(code), 8) if code[i:i+8] != original[i:i+8]] == [0x390],
                'synthetic program must change exactly one word')
        program.write_bytes(code)
        decode = subprocess.run([str(args.decoder), '-m', 'gf100', '-V', 'gk104', '-i', '-n',
                                 str(program)], capture_output=True, timeout=20)
        require(decode.returncode == 0, 'offline decode failed')
        listing = decode.stdout.decode('utf-8')
        require(any(row.startswith('00000390:') and row.endswith('join mov b32 $r9 $r6')
                    for row in listing.splitlines()), 'unexpected decoded operation')
        require(current.verify_decoder(code, listing, args.decoder), 'pinned decoder replay failed')
        before = previous.sass_contract(code, listing, 0)
        after = current.sass_contract(code, listing, 0)
        require(before.get('qualified') and before.get('old_register') == 9 and
                before.get('expected_register') == 0 and not after.get('qualified'),
                'counterexample verdict differs')
        result = {'status': 'PASS', 'previous_recognizer_SHA256': digest(args.previous.read_bytes()),
                  'current_recognizer_SHA256': digest(Path(current.__file__).read_bytes()),
                  'assembler_SHA256': digest(args.assembler.read_bytes()),
                  'decoder_SHA256': digest(args.decoder.read_bytes()),
                  'synthetic_program_SHA256': digest(code), 'synthetic_listing_SHA256': digest(decode.stdout),
                  'synthetic_changed_offset': '0x390', 'changed_operation': 'join mov b32 $r9 $r6',
                  'previous_accepted': True, 'current_accepted': False,
                  'original_AIR_and_synthetic_program_are_not_proven_related': True,
                  'original_regressions': regressions, 'GPU_dispatches': 0}
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
