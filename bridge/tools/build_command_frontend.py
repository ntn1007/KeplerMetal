#!/usr/bin/env python3
"""Build an isolated opt-in MSL compute-command AIR→NIR→SM30 backend.

No GPU access; vendor sources and the qualified SDK remain unchanged.
Each invocation creates a new immutable evidence directory.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import shlex
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / 'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5'
ARCHIVES = [
    'src/nouveau/compiler/libnak.a', 'src/nouveau/compiler/libnak_rs.a',
    'src/compiler/nir/libnir.a', 'src/compiler/libcompiler.a',
    'src/nouveau/headers/libnvidia_headers_c.a', 'src/util/libmesa_util.a',
    'src/util/libmesa_util_simd.a', 'src/util/blake3/libblake3.a',
    'src/c11/impl/libmesa_util_c11.a', 'src/compiler/rust/libcompiler_c_helpers.a',
    'src/compiler/rust/libcompiler_bindings.a',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError(f'Expected one source anchor: {before[:80]}')
    return text.replace(before, after, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=ROOT / 'src/gpu_command_frontend.metal')
    parser.add_argument('--entry', default='encode_public_compute_command')
    parser.add_argument('--ir-version', type=int, choices=[1,2], default=1)
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    out.mkdir(exist_ok=False)
    commands = []

    def run(command, label, cwd=ROOT, acceptable=(0,)):
        start = time.monotonic()
        result = subprocess.run([str(x) for x in command], cwd=cwd,
                                capture_output=True, text=True, timeout=55)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        commands.append({'label': label, 'argv': [str(x) for x in command],
                         'cwd': str(cwd), 'exit_code': result.returncode,
                         'wall_seconds': time.monotonic() - start})
        (out / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        print(label, result.returncode, flush=True)
        if result.returncode not in acceptable:
            raise RuntimeError(result.stderr[-6000:] or f'{label}: {result.returncode}')
        return result

    source = ROOT / 'results/cas-lowering-final/source-fork/tools/nakc/air_nir.c'
    assert sha(source) == '049edf24517d3bbbe3eaec437fcda381d28102853384abf9e2ee3f50d7f6ea9a'
    original = UPSTREAM / 'tools/nakc/air_nir.c'
    original_hash = sha(original)
    assert original_hash == 'b95f799f5af7857a5e1b2606d222c9aaae7a5e97086b99191d2bbdf07e14c992'
    fork = out / 'source-fork/tools/nakc'
    fork.mkdir(parents=True)
    text = source.read_text()
    text = replace_once(text,
        'static nir_def *arg(ctx *c, const air_inst *in, uint32_t i) { return getd(c, in->ops[1 + i]); }',
        'static nir_def *arg(ctx *c, const air_inst *in, uint32_t i) { return getd(c, in->ops[1 + i]); }\n'
        '#include "opennvda-command-ir.inc"')
    text = replace_once(text, '    if (!name) return indirect_call(c, in);',
                        '    if (!name) return indirect_call(c, in);\n'
                        '    if (lower_compute_command_ir(c, in, name)) return r;')
    text = replace_once(text, 'nir_block *nb = nir_block_create(c->s);',
                        'nir_block *nb = nir_block_create(c->impl);')
    (fork / 'air_nir.c').write_text(text)
    header = (UPSTREAM / 'tools/nakc/air_nir.h').read_text()
    header = replace_once(header, '} air_abi;',
                          '    uint32_t command_ir_version; /* zero unless opt-in command backend used */\n} air_abi;')
    header = replace_once(header, '} air_variant;',
                          '    uint32_t command_ir_v1; /* experimental portable command ABI, opt-in */\n} air_variant;')
    (fork / 'air_nir.h').write_text(header)
    for name in ['opennvda-command-ir.inc', 'KeplerCommandIR.h']:
        shutil.copyfile(ROOT / 'src' / name, fork / name)

    harness = (ROOT / 'tools/air_cas_compile.c').read_text()
    harness = replace_once(harness,
        '    if(argc!=6){fprintf(stderr,"usage: air_cas_compile INPUT.air OUTDIR ENTRY LOCAL CONSTANT_BANK\\n");return 2;}',
        '    if(argc!=7){fprintf(stderr,"usage: air_command_compile INPUT.air OUTDIR ENTRY LOCAL CONSTANT_BANK COMMAND_IR_V1\\n");return 2;}\n'
        '    if(strcmp(argv[6],"0") && strcmp(argv[6],"1") && strcmp(argv[6],"2"))return 2;')
    harness = replace_once(harness, 'air_variant variant={.block={local,1,1}};',
                          'air_variant variant={.block={local,1,1},.command_ir_v1=(unsigned)(argv[6][0]-\'0\')};')
    harness = replace_once(harness, '\\"gpu_execution\\":false}\\n',
                          '\\"command_ir_version\\":%u,\\"gpu_execution\\":false}\\n')
    harness = replace_once(harness, 'binary->info.slm_size,binary->info.crs_size);',
                          'binary->info.slm_size,binary->info.crs_size,abi.command_ir_version);')
    harness_file = out / 'air_command_compile.c'
    harness_file.write_text(harness)
    build = ROOT / 'build/mesa'
    entry = next(x for x in json.loads((build / 'compile_commands.json').read_text())
                 if x['file'].endswith('/nak_nir.c'))
    flags = [x for x in shlex.split(entry['command'])[1:]
             if x.startswith(('-I', '-D', '-std', '-f', '-W')) and not x.startswith('-Werror')]
    flags = ['-I' + str(fork)] + flags + [
        '-I' + str(UPSTREAM / 'drivers/NVMTLDriver/air'),
        '-Werror=implicit-function-declaration',
    ]
    objects = []
    for name, path in [('harness', harness_file), ('air_nir', fork / 'air_nir.c')]:
        obj = out / (name + '.o')
        run(['clang', '-O1', *flags, '-c', path, '-o', obj], 'compile-' + name, build)
        objects.append(obj)
    reader_objects = [ROOT / ('build/air-' + n + '.o') for n in ['bitstream', 'airir', 'metallib']]
    compiler = out / 'air_command_compile'
    run(['clang', '-o', compiler, *objects, *reader_objects, *ARCHIVES,
         '-lz', '-lpthread', '-lc++', '-framework', 'CoreFoundation', '-framework', 'Security'],
        'link-offline', build)
    msl = out / 'gpu_command_frontend.metal'
    msl_source=args.source.resolve()
    msl_source.relative_to(ROOT / 'src')
    shutil.copyfile(msl_source, msl)
    air = out / 'producer.air'
    run(['xcrun', '-sdk', 'macosx', 'metal', '-std=macos-metal2.3', '-c', msl, '-o', air], 'metal')
    run(['xcrun', '-sdk', 'macosx', 'metallib', air, '-o', out / 'producer.metallib'], 'metallib')
    reader = ROOT / 'results/gpu-command-frontend-inspection-20261015/metallib_air_dump'
    typed = run([reader, air, args.entry], 'typed-air')
    (out / 'typed-air.json').write_text(json.dumps(json.loads(typed.stdout), indent=2) + '\n')
    negative = out / 'backend-disabled'
    negative.mkdir()
    result = run([compiler, air, negative, args.entry, '32', '2', '0'],
                 'backend-disabled', acceptable=(10,))
    assert 'compute-command IR backend is disabled: air.reset_compute_command' in result.stderr
    positive = out / 'backend-enabled'
    positive.mkdir()
    result = run([compiler, air, positive, args.entry, '32', '2', str(args.ir_version)],
                 'backend-enabled')
    info = json.loads(result.stdout)
    (positive / 'info.json').write_text(json.dumps(info, indent=2) + '\n')
    assert info['sm'] == 30 and info['command_ir_version'] == args.ir_version
    assert info['buffer_slots'] == 1 and info['grid_offset'] == 8 and info['push_bytes'] == 32
    assert info['shared_bytes'] == 0 and info['scratch_bytes'] == 0 and info['crs_bytes'] == 0
    assert info['registers'] <= 63 and info['code_bytes'] <= 32768
    assert sha(original) == original_hash
    inputs = [Path(__file__).resolve(), source, original, UPSTREAM / 'tools/nakc/air_nir.h',
              ROOT / 'src/opennvda-command-ir.inc', ROOT / 'src/KeplerCommandIR.h',
              msl_source, ROOT / 'tools/air_cas_compile.c',
              reader, *reader_objects, *[build / x for x in ARCHIVES]]
    (out / 'manifest.json').write_text(json.dumps({
        'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'compiler_SHA256': sha(compiler), 'original_source_unchanged': True,
        'input_SHA256': {str(x): sha(x) for x in inputs},
        'fork_SHA256': {str(x.relative_to(out)): sha(x) for x in fork.iterdir()},
        'info': info, 'entry': args.entry, 'gpu_execution': False, 'status': 'PASS',
        'scope': 'Offline opt-in public MSL command intrinsics to portable command records, not native Apple ICB layout',
    }, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'out': str(out), 'info': info}, indent=2))


if __name__ == '__main__':
    main()
