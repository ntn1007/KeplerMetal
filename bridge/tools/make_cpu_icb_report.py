#!/usr/bin/env python3
"""Reconcile qualified CPU ICB evidence without launching hardware experiments."""
from pathlib import Path
import datetime, hashlib, json, subprocess

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT.parent / 'driver-research-2026-10-13'
OUT = ROOT / 'results/cpu-icb-progress'
OUT.mkdir(exist_ok=True)


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


protocol = read(ROOT / 'results/cpu-icb-weak-gpu-qualified/independent-verification.json')
lifetime = read(ROOT / 'results/cpu-icb-lifetime-readback-gpu-qualified/independent-verification.json')
assert protocol['status'] == lifetime['status'] == 'PASS'
assert protocol['user_GPU_invocations'] == 4396 and protocol['correct_uint32_words'] == 17584
assert lifetime['GPU_user_invocations'] == 198 and lifetime['correct_uint32_words'] == 792
assert protocol['host_executable_SHA256_rechecked'] and lifetime['host_executable_SHA256_rechecked']
assert not protocol['ICB_contract_complete'] and not lifetime['ICB_contract_complete']
cohorts = ['cpu-icb-prepared', 'cpu-icb-prepared-runtime', 'cpu-icb-prepared-retained',
           'cpu-icb-gpu-qualified', 'cpu-icb-weak-prepared', 'cpu-icb-weak-gpu-qualified',
           'cpu-icb-lifetime-prepared', 'cpu-icb-lifetime-gpu-qualified',
           'cpu-icb-lifetime-readback-prepared', 'cpu-icb-lifetime-readback-gpu-qualified']
history = []
ps = subprocess.check_output(['ps', '-axo', 'pid,stat,command'], text=True)
for name in cohorts:
    folder = ROOT / 'results' / name
    process = read(folder / 'execution/manifest.json')
    assert not process['authoritative_ps_status'] and not process['SIGKILL_requested']
    live = [line for line in ps.splitlines()
            if process['signed_executable'] in line or process['original_executable'] in line]
    assert not live, (name, live)
    history.append({'cohort': name, 'pid': process['pid'], 'exit_code': process['exit_code'],
                    'source_hashes': read(folder / 'inputs.json')['source_hashes'],
                    'terminal': True, 'results_available': (folder / 'results.json').is_file()})
assert [h['exit_code'] for h in history] == [-6, -11, 0, 0, 0, 0, 0, 17, 0, 0]
failure_notes = {
    'cpu-icb-prepared': 'Unavailable descriptor getter supportDynamicAttributeStride; fixed with respondsToSelector guard. No user command buffer submission.',
    'cpu-icb-prepared-runtime': 'Own-process objc_release/autorelease-pool crash after encoding. C IMP new-family ownership fixed with NS_RETURNS_RETAINED. No user command buffer submission.',
    'cpu-icb-lifetime-gpu-qualified': 'Exit17 at post-completion weak output/counter acquisition. No final GPU oracle captured. Corrected by encoding readback before completion; failed files preserved.'}
for row in history:
    if row['cohort'] in failure_notes:
        row['qualification'] = 'FAIL_PRESERVED'
        row['note'] = failure_notes[row['cohort']]

baseline = read(RESEARCH / 'reports/STRATEGIE_PREUVES.json')
checked = []
for entry in baseline['system_files']:
    actual = sha(Path(entry['path']))
    assert actual == entry['sha256'], entry['path']
    checked.append({'path': entry['path'], 'sha256': actual})
rootpatch = Path('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')
assert sha(rootpatch) == baseline['rootpatch_sha256'] and len(checked) == 83
inputs = [ROOT / p for p in [
    'src/KeplerCPUICB.h', 'src/KeplerCPUICB.mm', 'src/KeplerNativeCommands.h',
    'src/KeplerNativeCommands.mm', 'tools/cpu_icb_probe.mm',
    'tools/cpu_icb_lifetime_probe.mm', 'tools/reproduce_cpu_icb.py',
    'tools/reproduce_cpu_icb_lifetime.py', 'tools/verify_cpu_icb.py',
    'tools/verify_cpu_icb_lifetime.py', 'tools/run_signed_probe.py',
    'results/cpu-icb-weak-gpu-qualified/independent-verification.json',
    'results/cpu-icb-lifetime-readback-gpu-qualified/independent-verification.json',
    'results/native-nop-record-qualified/independent-verification.json']]
inputs.append(Path(__file__).resolve())
summary = {'captured_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'goal_turn': 'PROGRESS', 'goal_complete': False, 'integration_level': 1,
           'current_module_protocol_GPU_submissions': 7, 'protocol_GPU_invocations': 4396,
           'protocol_correct_uint32_words': 17584, 'lifetime_GPU_submissions': 2,
           'lifetime_GPU_invocations': 198, 'lifetime_correct_uint32_words': 792,
           'guard_mismatches': 0, 'CPU_ICB_public_selector_subset': True,
           'ICB_contract_complete': False, 'GPU_generated_ICB': False,
           'GPU_resident_command_indirection': False, 'native_GPU_program_changed': False,
           'performance_benchmark': False, 'system_modified': False,
           'system_files_unchanged': 83, 'rootpatch_unchanged': True,
           'all_children_terminal': True, 'signed_children': len(history),
           'successful_children': 7, 'failed_children_preserved': 3,
           'Qwen_job_ids': [], 'Git_branch': 'main', 'Git_commit': None,
           'scope': 'Process-local CPU-recorded compute selectors, pinned native consume_grid '
                    'pipeline, serial encoder and 1D grid. General Metal ICB, rendering, '
                    'arbitrary shaders, GPU generation, L2/L3, video/power/display and global '
                    'hardware qualification remain incomplete.'}
(OUT / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(OUT / 'verification-history.json').write_text(json.dumps(history, indent=2) + '\n')
provenance = {'macOS': subprocess.check_output(['sw_vers'], text=True),
              'clang': subprocess.check_output(['clang++', '--version'], text=True),
              'SDK_path': subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], text=True).strip(),
              'Git_status': subprocess.check_output(['git', 'status', '--short', '--branch'], cwd=ROOT.parent.parent, text=True),
              'inputs': [{'path': str(p), 'sha256': sha(p)} for p in inputs],
              'system_files': checked, 'rootpatch_sha256': sha(rootpatch),
              'system_modifications': False, 'Qwen_job_ids': []}
(OUT / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')

coverage_path = ROOT / 'results/hardware-coverage.json'
coverage = read(coverage_path)
assert not coverage['complete']
for row in coverage['coverage']:
    if row['category'] == 'Persistent recorded native compute packets and mixed resources':
        row['remaining_requirements'] = ('Current process-local CPU compute selector subset is qualified separately. '
            'Full CPU ICB states/resources, render/indirect ranges/GPU timeline operations, GPU-resident '
            'indirection/generation, arbitrary shaders, concurrency/stress, benchmarks and L2/L3 remain open.')
category = 'CPU-recorded compute ICB selectors and bounded resource lifetime'
new_row = {'category': category, 'status': 'partially_functional_application_local',
           'tested_scope': 'Current module:7GPU user command buffers,4396invocations,17584uint32; '
               'ranges/reuse/reset/CPU snapshot copy/rebinding. Two lifetime submissions:198invocations,792uint32; '
               'ICB/scope released before commit, device restored, ended encoders released; unretained private '
               'negative never submitted. Same pinned native pipeline, serial encoder; no new GPU shader.',
           'remaining_requirements': 'Full CPU ICB contract including general pipeline/binding qualification, '
               'inherited states, threadgroup memory/nonuniform grids, render, GPU-timeline reset/copy/optimize, '
               'indirect range/resourceID/GPU generation, residency/concurrency/stress/benchmarks and L2/L3. '
               'Metadata GPU buffer currently accounts for resource ownership, not a GPU-readable ICB command layout.',
           'evidence': ['src/KeplerCPUICB.h', 'src/KeplerCPUICB.mm',
               'results/cpu-icb-weak-gpu-qualified/independent-verification.json',
               'results/cpu-icb-lifetime-readback-gpu-qualified/independent-verification.json',
               'results/cpu-icb-progress/summary.json', 'CPU_ICB_NATIF.txt']}
coverage['coverage'] = [r for r in coverage['coverage'] if r['category'] != category] + [new_row]
coverage_path.write_text(json.dumps(coverage, indent=2) + '\n')
(RESEARCH / 'inventory/evidence-summaries/hardware-coverage.json').write_bytes(coverage_path.read_bytes())
print(json.dumps(summary, indent=2))
