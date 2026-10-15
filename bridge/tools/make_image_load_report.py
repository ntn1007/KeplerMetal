#!/usr/bin/env python3
"""Recompute image-load expectations from immutable raw dumps, independently."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct
import sys

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--input', type=Path, default=root/'results/image-load-final')
parser.add_argument('--check-only', action='store_true', help='Verify raw artifacts without changing reports or coverage')
args = parser.parse_args()
folder = args.input.resolve()
folder.relative_to(root/'results')
manifest = json.loads((folder/'manifest.json').read_text())
assert manifest['driver_unchanged'] and (not manifest['quick'] or args.check_only)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

assert sha(folder/'carrier.metallib') == manifest['carrier_sha256']
assert sha(folder/'libKeplerProgramImport.dylib') == manifest['library_sha256']
for artifact in manifest['source_snapshot'] + manifest['shaders']:
    assert sha(root/artifact['path']) == artifact['sha256']

def hash32(value):
    value ^= value >> 16
    value = (value * 0x7feb352d) & 0xffffffff
    value ^= value >> 15
    value = (value * 0x846ca68b) & 0xffffffff
    return value ^ (value >> 16)

scales = (.5, -1.5, 2., .25)
biases = (.125, -.25, .5, -.75)
control_values = (.25, .5, .75, 1.)
markers = (0x1234, 0x5678, 0xabcd, 0xeffe)
formats = {'rgba32f': (16, 4, '<4f'), 'rgba16f': (8, 2, '<4e'),
           'rgba8': (4, 1, '<4B'), 'r32f': (4, 1, '<f')}
records = []
paired = {}
maximum_errors = {name: 0. for name in formats}
pixels_by_mode = {'nak': 0, 'reference': 0, 'control': 0}
oob_by_mode = dict.fromkeys(pixels_by_mode, 0)
fixture_keys = set()
for case in manifest['cases']:
    assert case['exit_code'] == 0
    result = json.loads((root/case['result']).read_text())
    fmt, mode = result['format'], result['mode']
    W, H = result['texture_shape']
    OW, OH = result['output_shape']
    variant = result['variant']
    staging = result['staging']
    assert fmt in formats and mode in pixels_by_mode
    assert (W, H) in ((64, 48), (33, 17)) and variant in (0, 1)
    assert staging in ('managed', 'nocopy')
    assert (OW, OH) == (W + 2*variant, H + 2*variant)
    key = (fmt, W, H, variant, staging, mode)
    assert key not in fixture_keys
    fixture_keys.add(key)
    assert result['device'] == 'NVIDIA GeForce GTX 880M'
    assert result['command_status'] == 4
    assert result['mismatches'] == result['raw_mismatches'] == result['guard_mismatches'] == 0
    if mode == 'nak':
        proof = result['import']
        assert proof['contract_verified']
        assert proof['device'] == result['device'] and proof['registry_id'] == result['registry_id']
        assert len(proof['events']) == 1
        event = proof['events'][0]
        shader = next(s for s in manifest['shaders'] if s['format'] == fmt)
        assert event['imported_code_identical'] and event['code_replaced']
        assert event['valid_container'] and event['stage'] == 5
        assert event['decoded_code_bytes'] == shader['info']['code_bytes']
        assert event['decoded_registers'] == shader['info']['registers']
        assert event['launch_words_9_11'] == [576, 576]
    prefix = folder/(case['label'] + '-data')
    paths = [Path(str(prefix) + suffix) for suffix in ('.source.bin', '.output.bin', '.raw.bin')]
    source, output, raw = (p.read_bytes() for p in paths)
    pixel_bytes, raw_components, encoding = formats[fmt]
    row = (W*pixel_bytes + 255) & ~255
    assert row == result['input_bytes_per_row'] and pixel_bytes == result['pixel_bytes']
    assert len(source) == row*H
    assert len(output) == len(raw) == OW*OH*16 + 128
    for buffer in (output, raw):
        assert buffer[:64] == buffer[-64:] == bytes([0xa5])*64
    # Check deterministic input construction and row padding independently.
    for sy in range(H):
        for sx in range(W):
            pixel = sy*W+sx
            n = 1 if fmt == 'r32f' else 4
            expected_input = bytearray()
            for c in range(n):
                h = hash32(pixel*4+c+0x185f39a5)
                if fmt == 'rgba8': expected_input += struct.pack('<B', h & 255)
                elif fmt == 'rgba16f': expected_input += struct.pack('<H', (h & 0x8000)|0x3800|(h & 0x7ff))
                else: expected_input += struct.pack('<f', ((h & 2047)-1024)/256.)
            offset = sy*row+sx*pixel_bytes
            assert source[offset:offset+pixel_bytes] == expected_input
        assert source[sy*row+W*pixel_bytes:(sy+1)*row] == bytes([0xee])*(row-W*pixel_bytes)
    maximum = 0.
    oob_pixels = 0
    for y in range(OH):
        for x in range(OW):
            sx, sy = x-variant, y-variant
            inside = 0 <= sx < W and 0 <= sy < H
            oob_pixels += not inside
            if inside:
                packed = source[sy*row+sx*pixel_bytes:sy*row+(sx+1)*pixel_bytes]
                values = struct.unpack(encoding, packed)
                if fmt == 'rgba8': values = tuple(v/255. for v in values)
                if fmt == 'r32f': values = (values[0], 0., 0., 1.)
                raw_values = struct.unpack('<'+'I'*raw_components, packed) + (0,)*(4-raw_components)
            else:
                values = (0.,)*4
                raw_values = (0,)*4
            offset = 64+(y*OW+x)*16
            actual = struct.unpack_from('<4f', output, offset)
            actual_raw = struct.unpack_from('<4I', raw, offset)
            expected = tuple(control_values[c]+biases[c] if mode == 'control' else values[c]*scales[c]+biases[c] for c in range(4))
            for got, want in zip(actual, expected):
                assert math.isfinite(got)
                error = abs(got-want)
                assert error <= 2e-6, (case['label'], x, y, got, want)
                maximum = max(maximum, error)
            if mode == 'nak': assert actual_raw == raw_values, (case['label'], x, y, actual_raw, raw_values)
            elif mode == 'control': assert actual_raw == markers
            else: assert actual_raw == (0xa5a5a5a5,)*4
    assert oob_pixels == result['out_of_bounds_pixels']
    assert OW*OH == result['pixels_checked']
    assert abs(maximum-result['maximum_float_error']) <= 1e-12
    maximum_errors[fmt] = max(maximum_errors[fmt], maximum)
    pixels_by_mode[mode] += OW*OH
    oob_by_mode[mode] += oob_pixels
    paired[(fmt, W, H, variant, staging, mode)] = output[64:-64]
    records.append({**case, 'format': fmt, 'mode': mode, 'texture_shape': [W, H],
                    'output_shape': [OW, OH], 'variant': variant, 'staging': staging,
                    'pixels': OW*OH, 'oob_pixels': oob_pixels, 'maximum_cpu_error': maximum,
                    'raw_artifacts': [{'path': str(p.relative_to(root)), 'sha256': sha(p)} for p in paths]})
assert len(records) == (12 if manifest['quick'] else 96)
sizes = ((64,48),) if manifest['quick'] else ((64,48),(33,17))
variants = (0,) if manifest['quick'] else (0,1)
stagings = ('nocopy',) if manifest['quick'] else ('managed','nocopy')
expected_keys = {(fmt, W, H, variant, staging, mode) for fmt in formats for W,H in sizes
                 for variant in variants for staging in stagings for mode in pixels_by_mode}
assert fixture_keys == expected_keys
native_differences = dict.fromkeys(formats, 0.)
for key, value in paired.items():
    if key[-1] != 'nak': continue
    native = paired[key[:-1]+('reference',)]
    # The untouched carrier is a negative control for shader substitution.
    assert value != paired[key[:-1]+('control',)]
    differences = [abs(a[0]-b[0]) for a,b in zip(struct.iter_unpack('<f', value), struct.iter_unpack('<f', native))]
    native_differences[key[0]] = max(native_differences[key[0]], max(differences))
    assert max(differences) <= 2e-6

if args.check_only:
    print(json.dumps({'cases': len(records), 'independent_raw_byte_oracle_passed': True,
                      'maximum_CPU_error_by_format': maximum_errors,
                      'maximum_NAK_native_difference_by_format': native_differences}, indent=2))
    sys.exit(0)

ledger_path = root/'results/hardware-coverage.json'
ledger = json.loads(ledger_path.read_text())
updates = []
additions = {
    'Texture/sampler/surface units': 'Raw 2D surface loads via nir_suldga_nv (Envytools SULDGB.cg.zero), B32/B64/B128, explicit unpack to RGBA32Float/RGBA16Float/RGBA8Unorm/R32Float;32 NAK fixtures plus32 native read controls and32 substitution controls;64x48/33x17, border coordinates -1 through width/height, partial4x8 groups; exact raw words and independent CPU transformed float oracle; Managed/NoCopy staging',
    'Application-local native program import': 'Compute surface-load carrier with buffer7/8 addresses observed at CB1[0xe8]/[0x108], CB2 scale/bias/shape; distinct native reference and unchanged-carrier negative control; code-byte identity and SM30 metadata checked for four load programs',
    'CPU/GPU memory and DMA': 'Private 2D texture upload and Private float/raw output buffers followed by GPU blit readback;256-byte aligned input rows;64-byte prefix/suffix guards, Managed synchronization/NoCopy staging;96 load/reference/control fixtures'
}
for category, addition in additions.items():
    row_data = next(r for r in ledger['coverage'] if r['category'] == category)
    if addition not in row_data['tested_scope']: row_data['tested_scope'] += '; '+addition
    for evidence in ('results/image-load-summary.json', str((folder/'manifest.json').relative_to(root)),
                     'tools/image_load_compile.c', 'tools/image_load_probe.mm', 'tools/make_image_load_report.py', 'LECTURE_IMAGES.txt'):
        if evidence not in row_data['evidence']: row_data['evidence'].append(evidence)
    if category == 'Texture/sampler/surface units':
        row_data['remaining_requirements'] = 'Further bindings/dimensions/mips/formats, image atomics, gather/compression/coherency; signed/special/subnormal/overflow conversion conformance; general read_write API support remains unqualified'
    updates.append(row_data)
summary = {'collected_at': manifest['collected_at'], 'cases': len(records), 'NAK_cases': 32,
           'pixels_by_mode': pixels_by_mode, 'out_of_bounds_pixels_by_mode': oob_by_mode,
           'maximum_CPU_error_by_format': maximum_errors, 'maximum_NAK_native_difference_by_format': native_differences,
           'raw_mismatches': 0, 'guard_mismatches': 0, 'independent_raw_byte_oracle_passed': True,
           'driver_unchanged': True, 'driver_sha256': manifest['driver_sha256'], 'performance_benchmark': False,
           'oracle_source': str(Path(__file__).resolve().relative_to(root)), 'oracle_source_sha256': sha(Path(__file__)),
           'shaders': manifest['shaders'], 'records': records, 'coverage_updates': updates, 'global_hardware_goal_complete': False}
ledger['complete'] = False
ledger_path.write_text(json.dumps(ledger, indent=2)+'\n')
(root/'results/image-load-summary.json').write_text(json.dumps(summary, indent=2)+'\n')
lines = ['KEPLERMETAL — lectures d’images par NAK sur GTX 880M', '',
         '96 essais passent :32 NAK,32 Metal natifs de référence et32 témoins sans',
         'substitution du code. Les deux témoins utilisent des shaders distincts.',
         'Chaque famille couvre64×48/33×17, avec/sans bord extérieur, Managed/NoCopy.',
         'La texture et les buffers de sortie sont Private ; upload et lecture par blit.',
         'Les coordonnées extérieures sont -1 et width/height ; les groupes partiels',
         'sont bornés avant d’écrire les buffers. Les sorties brutes hors image valent0.',
         'Toutes les gardes64B et les mots bruts passent les comparaisons exactes.',
         'Python relit les dumps et recalcule les entrées, le décodage et les résultats',
         'indépendamment de la sonde Objective-C++ ; les empreintes sont conservées.', '',
         'FORMAT       ERREUR MAX CPU         ÉCART MAX NAK/METAL NATIF']
for fmt in formats:
    lines.append(f'{fmt:12} {maximum_errors[fmt]:.12g}          {native_differences[fmt]:.12g}')
lines += ['', f'Pixels NAK contrôlés : {pixels_by_mode["nak"]}, dont {oob_by_mode["nak"]} hors limites.',
          'RGBA32F/R32F : valeurs finies dyadiques signées ; RGBA16F : normales finies',
          'signées ; RGBA8 : UNORM. NaN/Inf/subnormaux ne sont pas qualifiés.',
          'L’intrinsèque nir_suldga_nv produit des lectures brutes B32/B64/B128,',
          'décodées SULDGB.cg.zero par Envytools ; NIR décode explicitement',
          'le format. Ce résultat ne qualifie pas une instruction de lecture typée.',
          'Le shader porteur déclare une texture access::write afin que le pilote',
          'produise son descripteur de surface habituel ; la branche d’écriture est',
          'inaccessible dans ces fixtures. Cela ne change aucune capacité Metal.',
          'Le shader NAK remplace uniquement le programme de notre processus.',
          'Metal fournit les ressources, les commandes et les fences via le pilote',
          'installé. Le témoin sans substitution produit des marqueurs différents.',
          'Le statut Completed, l’identité du GPU et une allocation seuls ne sont',
          'pas utilisés comme preuve : identité du code et résultats sont vérifiés.',
          'Aucun gain de performances mesuré ; aucune nouvelle famille Metal annoncée.', '',
          'REPRODUCTION',
          'Depuis le dossier bridge, avec Mesa/libKeplerProgramImport déjà construits :',
          'python3 tools/reproduce_image_load.py --out results/image-load-reproduction',
          'python3 tools/make_image_load_report.py --input results/image-load-reproduction',
          'Le dossier de reproduction doit être nouveau. Le lanceur signe une copie',
          'locale des exécutables ; les fichiers système restent inchangés.',
          'Mesa26.2.4 commit96cb43121031992b85767f9c1be8f3f48e22b1d2 ; correctifs',
          'Darwin/embedding/texture et atomic64 conservés. Les commandes de compilation,',
          'sources figées, captures natives, binaires et métadonnées se trouvent dans :',
          str(folder.relative_to(root))+'/manifest.json et commands.json', '',
          'Empreintes SHA256 des programmes NAK :']
for shader in manifest['shaders']: lines.append(shader['format']+' : '+shader['sha256'])
lines += ['', 'Pilote inchangé : '+manifest['driver_sha256'],
          'Ni macOS, ni OCLP, ni les protections, ni le VBIOS/horloges/registres modifiés.',
          'Couverture matérielle complète toujours ouverte : results/hardware-coverage.json.']
(root/'LECTURE_IMAGES.txt').write_text('\n'.join(lines)+'\n')
print(json.dumps({k: summary[k] for k in ('cases','pixels_by_mode','out_of_bounds_pixels_by_mode',
                  'maximum_CPU_error_by_format','maximum_NAK_native_difference_by_format','driver_unchanged')}, indent=2))
