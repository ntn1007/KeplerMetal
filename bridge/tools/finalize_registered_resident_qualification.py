#!/usr/bin/env python3
"""Recheck recorded bytes and terminal processes; never dispatch GPU work."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results'
OUT = RESULTS / 'registered-resident-progress-20261014/final-qualification'
SDK = RESULTS / 'registered-resident-sdk-build-20261014-02/KeplerMetalSDK'


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def write(name, data):
    with (OUT / name).open('x') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def oracle(name, base):
    spec = importlib.util.spec_from_file_location(name, base / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify


def main():
    OUT.mkdir(exist_ok=False)
    modes = ['prepare', 'chain', 'range', 'chain_completed', 'range_completed', 'no_second']
    copy = oracle('verify_registered_resident_copy', ROOT / 'tools')
    bounds = oracle('verify_registered_resident_bounds', ROOT / 'tools')
    verifiers = {k: oracle(n, SDK / 'examples') for k, n in [
        ('async', 'verify_cpu_icb_copy_async'), ('mixed', 'verify_cpu_icb_copy_mixed'),
        ('graph', 'verify_cpu_icb_copy_graph'), ('baseline', 'verify_cpu_icb_gpu_copy'),
        ('refusal', 'verify_cpu_icb_copy_refusals'), ('reverse', 'verify_fp64_reverse_client'),
        ('arithmetic', 'verify_fp64_client'), ('cas', 'verify_example'),
        ('literal', 'verify_literal_client')]}
    checks, gtx_cases, m1_cases = [], [], []

    def check(p, fn, m1=False):
        v = fn(p)
        assert v['status'].startswith('PASS')
        checks.append({'path': str(p.relative_to(ROOT)), 'verification': v})
        (m1_cases if m1 else gtx_cases).append(p)
        return v

    positive = negative = raw_equal = 0
    m1_root = RESULTS / 'registered-resident-M1-return-20261014/GPUCopyReturn/results'
    for mode in modes:
        p = RESULTS / ('registered-resident-imac-' + mode + '-20261014')
        q = m1_root / mode
        a, b = check(p, copy), check(q, copy, True)
        assert a['exact_uint32_words'] == b['exact_uint32_words']
        assert b['CB0_sizes_qualified'] == []
        if mode == 'no_second':
            negative += a['exact_uint32_words']
        elif mode != 'prepare':
            positive += a['exact_uint32_words']
        assert a['raw_SHA256'] == b['raw_SHA256']
        raw_equal += len(a['raw_SHA256'])
    assert (positive, negative, raw_equal) == (150048, 25348, 108)

    bounds_words = 0
    for mode in ['prepare_short', 'copy_short']:
        p = RESULTS / ('registered-resident-bounds-' + mode + '-20261014')
        bounds_words += check(p, bounds)['exact_uint32_words']
    assert bounds_words == 50288

    nr_counts, raw_counts = {}, {}
    old_prefixes = {'async': 'resident-async-imac-', 'mixed': 'resident-async-regression-mixed-',
                    'graph': 'resident-async-regression-graph-', 'baseline': 'resident-async-regression-baseline-',
                    'refusal': 'resident-async-regression-refusal-'}
    comparisons = []
    for variant in ['async', 'mixed', 'graph', 'baseline', 'refusal']:
        paths = sorted(RESULTS.glob('registered-resident-regression-' + variant + '-*-20261014'))
        nr_counts[variant], raw_counts[variant] = len(paths), 0
        for p in paths:
            v = check(p, verifiers[variant])
            suffix = p.name[len('registered-resident-regression-' + variant + '-'):]
            old = RESULTS / (old_prefixes[variant] + suffix)
            for f in sorted((p / 'outputs').glob('*.bin')):
                ref = old / 'outputs' / f.name
                assert f.read_bytes() == ref.read_bytes(), (f, ref)
                comparisons.append({'current': str(f.relative_to(ROOT)),
                                    'previous': str(ref.relative_to(ROOT)), 'SHA256': sha(f)})
                raw_counts[variant] += 1
    assert nr_counts == {'async': 18, 'mixed': 21, 'graph': 21, 'baseline': 9, 'refusal': 4}
    assert raw_counts == {'async': 432, 'mixed': 540, 'graph': 540, 'baseline': 108, 'refusal': 144}
    assert len(comparisons) == 1764
    for name in ['reverse', 'arithmetic', 'cas', 'literal']:
        check(RESULTS / ('registered-resident-regression-' + name + '-20261014'), verifiers[name])
    assert len(gtx_cases) == 85 and len(m1_cases) == 6 and len(checks) == 91

    commands = read(RESULTS / 'registered-resident-nonregression-suite-20261014/commands.json')
    assert len(commands) == 81 and all(c['exit_code'] == 0 for c in commands)

    process_table = subprocess.run(['ps', '-axo', 'pid=,lstart=,command='], check=True,
                                   text=True, capture_output=True).stdout
    live_pids = {int(line.split()[0]): line for line in process_table.splitlines() if line.strip()}
    terminals = []
    for p in gtx_cases + m1_cases:
        m = read(p / 'execution/manifest.json')
        assert m['exit_code'] == 0 and not m['SIGKILL_requested']
        assert m['GPU_reservation']['state'] == 'terminal' and not m['authoritative_ps_status']
        if p in gtx_cases:
            # A recycled PID is not the process identity; never kill it.
            now = live_pids.get(m['pid'], '')
            assert not now or m['signed_executable'] not in now, now
            current = 'absent' if not now else 'PID_reused_by_different_command'
        else:
            current = 'recorded_remote_terminal; not re-polled on M1'
        terminals.append({'result': str(p.relative_to(ROOT)), 'PID': m['pid'],
                          'exit_code': 0, 'reservation': 'terminal', 'current_process_check': current})
    write('terminal-process-check.json', {'status': 'PASS', 'processes': terminals})

    manifest = read(SDK / 'FILE_MANIFEST.json')
    for e in manifest['files']:
        f = SDK / e['path']
        assert f.stat().st_size == e['bytes'] and sha(f) == e['SHA256']
    assert len(manifest['files']) + 1 == 142
    build = read(SDK / 'BUILD_MANIFEST.json')
    generated = []
    for n, h in build['source_SHA256'].items():
        canonical = ROOT / 'src' / n
        if canonical.exists():
            assert sha(canonical) == h
        else:
            assert n == 'KeplerFP64Programs.inc' and sha(SDK / 'src' / n) == h
            generated.append({'file': n, 'SHA256': h, 'origin': 'generated frozen SDK source'})
    library_sha = sha(SDK / 'lib/libKeplerMetal.a')
    assert library_sha == build['static_library_SHA256'] == '74991314fa82544212eacb506953fbcf57fcd0a95da1cecca046ab41945900ec'
    archive = SDK.parent / 'KeplerMetalSDK-combined-cb0-fp64-x86_64-2026-10-14.tar.gz'
    assert sha(archive) == 'd56511e3d55286a3928a5ffb6b6c61e190f58e3e1dda7d68cdff4caf337b786d'

    baseline = read(RESULTS / 'resident-submission-progress-20261014/system-check.json')
    for e in baseline['system_files']:
        assert sha(e['path']) == e['sha256'], e['path']
    assert len(baseline['system_files']) == 83
    assert sha(baseline['rootpatch_path']) == baseline['rootpatch_SHA256']
    system = dict(baseline)
    system.update(checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  status='PASS', system_files_unchanged=83, OCLP_rootpatch_unchanged=True)
    write('final-system-check.json', system)
    write('independent-rechecks.json', {'status': 'PASS', 'GPU_runs_started': 0, 'checks': checks})
    write('nonregression-raw-comparison.json', {'status': 'PASS', 'files_identical': 1764,
                                               'counts': raw_counts, 'files': comparisons})

    receipt = {'status': 'PASS', 'date': '2026-10-14',
        'objective': 'Toutes les fonctionnalites materielles de la GTX 880M sur macOS',
        'objective_complete': False, 'Git': {'branch': 'main', 'commit': None, 'state': 'UNBORN; lab untracked'},
        'job_ids': [], 'integration_level': 2, 'ordinary_applications_transparent': False,
        'SDK_archive_SHA256': sha(archive), 'static_library_SHA256': library_sha,
        'SDK_files_verified_including_manifest': 142, 'core_source_SHA256': build['source_SHA256'],
        'generated_source_checked_in_frozen_SDK': generated,
        'GTX_primary_cases': 6, 'GTX_bounds_cases': 2, 'GTX_nonregression_cases': 77,
        'M1_reference_cases': 6, 'primary_trials_per_case': 3,
        'independent_oracles_PASS': 91, 'positive_exact_uint32_words': positive,
        'negative_exact_uint32_words': negative, 'bounds_witness_exact_uint32_words': bounds_words,
        'M1_GTX_raw_files_identical': 108, 'nonregression_raw_files_identical': 1764,
        'GTX_native_CB0_sizes_qualified': [256, 512, 1024], 'M1_qualifies_NVIDIA_CB0_layout': False,
        'registered_binding_count': 4, 'native_registered_profiles_supported_without_three_name_allowlist': True,
        'same_library_and_registration_domain_required': True, 'dynamic_threadgroup_support': False,
        'GPU_generated_ICB': False, 'full_ICB_contract': False, 'performance_benchmark': False,
        'new_driver_installed': False, 'system_files_unchanged': 83, 'OCLP_rootpatch_unchanged': True,
        'FAIL': [], 'BLOCKED': [],
        'NOT_RUN': ['New-library performance benchmark', 'Transparent ordinary application integration',
                    'GPU-generated ICB', 'All registered resource layouts and shader configurations'],
        'next_action': 'Qualify more registered native layouts and geometry/shared-memory contracts, then reusable GPU command generation and application integration'}
    write('qualification-receipt.json', receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != 'core_source_SHA256'}, indent=2))


if __name__ == '__main__':
    main()
