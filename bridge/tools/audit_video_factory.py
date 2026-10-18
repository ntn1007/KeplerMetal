#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck pinned factory/policy observations; execute no vendor or GPU code.

The report contains scalar facts and hashes only. A completed diagnostic with
zero hardware images remains a hardware refusal, never a decoding success.
"""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
import subprocess

from audit_video_registry import correlate
from audit_video_local_service import owned, software
from native_video_factory import verify_owned
from verify_native_control_reserve import terminal


GVA_POLICY = '/System/Library/PrivateFrameworks/AppleGVA.framework/Resources/Info.plist'
GVA_POLICY_SHA = 'c7cefb08fe12c1da168d8baad6b92d341ff3e331a4d2c5011de5d36bff64b3e3'
GVA_UUID = 'ca5414f369373c059ea2d82b35afd4f0'
VT_UUID = 'e7231bea63883d0a95c0a93ce970b96b'
CM_UUID = '7c4ae5aed528396982c6a4a534949ef3'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def signed32(value):
    value &= 0xffffffff
    return value - 0x100000000 if value & 0x80000000 else value


def receipt(root, build, bridge):
    inp = terminal(root, bridge, build)
    frozen, manifest = load(build / 'inputs.json'), load(root / 'execution/manifest.json')
    require(inp['source_hashes'] == frozen['source_hashes']
            and inp['runtime_SHA256'] == frozen['runtime_SHA256'], 'run/build source identity')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in frozen[key].items():
            require(sha(build / folder / name) == digest, 'frozen source/asset/runner: ' + name)
    mutable = {'owned-choice.json', 'dependency-choice.json', 'factory-policy-choice.json'}
    for name, digest in frozen['assets_SHA256'].items():
        if name not in mutable:
            require(inp['assets_SHA256'][name] == digest, 'invariant asset: ' + name)
    require(sha(build / 'application') == frozen['executable_SHA256'] == inp['executable_SHA256'], 'build executable')
    for path, digest in frozen['reused_objects_and_libraries_SHA256'].items():
        require(sha(path) == digest, 'reused prerequisite')
    parent = Path(frozen['owned_build'])
    require(sha(parent / 'inputs.json') == frozen['owned_inputs_SHA256'], 'owned parent manifest')
    verify_owned(parent)
    for name, field in [('libVideoOwned.dylib', 'library_SHA256'),
                        ('libVideoRegistryMetadata.dylib', 'metadata_library_SHA256'),
                        ('libVideoFactoryResolver.dylib', 'resolver_library_SHA256')]:
        require(sha(build / name) == frozen[field], 'library: ' + name)
    for name, digest in frozen['new_objects_SHA256'].items():
        require(sha(build / name) == digest, 'new object')
    require(len(load(build / 'commands.json')) == 5
            and all(c['exit_code'] == 0 for c in load(build / 'commands.json')), 'five successful build commands')
    require(manifest['arguments'] == [str(root / 'assets'), str(root / 'outputs'), inp['mode']], 'executed arguments')
    now = subprocess.run(['ps', '-p', str(manifest['pid']), '-o', 'stat='], text=True, capture_output=True)
    require(not now.stdout.strip(), 'historical PID exists; recheck its birth before auditing')
    return inp, manifest


def factory_record(root, version, mode):
    d = load(root / 'factory-resolver.json')
    require(d == load(root / 'outputs/factory-resolver.json'), 'retained resolver output')
    require(d['status'] == 'COMPLETE' and d['recorders_drained'] and not d['dropped']
            and d['synthetic_controls_valid'], 'complete factory observation')
    for key in ['native_function_invoked_directly', 'resolved_pointer_replaced', 'arguments_modified',
                'original_instructions_modified', 'system_modified', 'hardware_video_execution_proved',
                'performance_benchmark']:
        require(d[key] is False, 'factory scope: ' + key)
    require(d['caller_module_UUID'] == CM_UUID and d['caller_return_offset'] == 135582, 'public resolver profile')
    require(d['synthetic_control_calls'] == len(d['controls']) == 32, 'resolver control count')
    for i, row in enumerate(d['controls']):
        require(row == dict(correct=True, trial=i, input_errno=500+i, output_errno=600+i,
                            result_present=bool(i % 3), native_resolver_called=False), 'resolver mock ABI/errno')
    public_count = int(mode == 'cpu' or (version >= 4 and mode == 'hardware'))
    require(d['calls'] == len(d['events']) == public_count, 'public resolver event count')
    for row in d['events']:
        require(row['result_present'] and not row['truncated'] and row['arguments_are_public_CF_types']
                and row['arguments_forwarded_unchanged'] and row['returned_pointer_unchanged']
                and not row['function_invoked_by_observer'], 'real public resolver forwarding')
        if mode == 'hardware':
            target = row['result_identity']
            require(row['caller_module'] == 'VideoToolbox' and row['caller_offset'] == 4294934
                    and row['name'] == 'AVFQTX_CreateMediaAcceleratorInterface'
                    and target['UUID'] == GVA_UUID and target['version'] == '10.0.20'
                    and target['offset'] == 4577 and target['symbol_exact_address'], 'actual GVA interface')
        else:
            require(row['name'] == 'H264VideoDecoder_CreateInstance', 'software factory name')
            # V1 did not accept MH_BUNDLE without LC_ID_DYLIB. Preserve its gap.
            if version >= 3:
                require(row['result_identity']['UUID'] == '85e6e70880dd3ccb9c8c31e2d40f812a'
                        and row['result_identity']['offset'] == 25296, 'software bundle identity')
    if version >= 3:
        require(d['factory_control_calls'] == len(d['factory_controls']) == 32, 'factory mock count')
        for i, row in enumerate(d['factory_controls']):
            require(row == dict(correct=True, trial=i, status=[-12692, 0, -12906][i % 3],
                                factory_present=bool(i % 3), input_errno=700+i, output_errno=800+i,
                                original_private_function_called=False), 'private forwarding mock ABI/errno/out slot')
        require(d['factory_calls'] == len(d['factory_events']) == int(mode != 'inspect'), 'natural GetFactory count')
        for row in d['factory_events']:
            require(row['status_int32'] == 0 and row['factory_present'] and row['allow_load_uint32'] == 1
                    and row['original_caller_offset'] == 6289489 and row['factory_pointer_unchanged']
                    and row['typed_out_slot_observed_after_original']
                    and row['original_forwarded_through_qualified_entry_tail']
                    and not row['opaque_item_dereferenced_by_observer']
                    and not row['original_caller_return_address_preserved']
                    and not row['returned_factory_invoked_by_observer'], 'natural factory result')
            target = row['factory_identity']
            require(target['offset'] == (25296 if mode == 'cpu' else 4294856), 'factory target offset')
            if mode == 'hardware':
                require(target['UUID'] == VT_UUID, 'VT factory identity')
                if version >= 4:
                    require(not target['symbol_exact_address']
                            and target['nearest_symbol_image_offset'] == 4277198, 'nearest symbol is not factory identity')
    return d


def case(root, build, bridge, version, mode, choice='observe'):
    inp, m = receipt(root, build, bridge)
    require(inp['mode'] == mode and inp['route'] == ('native' if mode == 'inspect' else 'owned'), 'case mode/route')
    result, own = load(root / 'results.json'), load(root / 'owned.json')
    reached = mode != 'inspect'
    owned(own, m, reached)
    f = factory_record(root, version, mode)
    row = dict(case=root.name, version=version, mode=mode, policy=choice, PID=m['pid'],
               started_at=m['started_at'], completed_at=m['completed_at'], diagnostic_status='PASS',
               frames=0, pixel_bytes=0, policy_calls=0, policy_substitutions=0,
               software_nonzero_native_replies=0,
               manifest_SHA256=sha(root / 'execution/manifest.json'), result_SHA256=sha(root / 'results.json'),
               factory_SHA256=sha(root / 'factory-resolver.json'), original_binary_SHA256=m['original_binary_sha256'],
               signed_binary_SHA256=m['signed_binary_sha256'], resolver_controls=32,
               GetFactory_controls=32 if version >= 3 else 0)
    if mode == 'inspect':
        require(result['public_decode'] is None and not result['trace']['calls'], 'inspect ran decoder')
    else:
        dep, meta = load(root / 'dependency.json'), load(root / 'metadata.json')
        require(dep['status'] == 'COMPLETE' and dep['recorders_drained'] and not dep['pending'] and not dep['dropped']
                and dep['public_query_controls_valid'] and dep['hardware_requirement_preserved']
                and not dep['system_modified'], 'dependency capture')
        require(dep['original_specification'] == ({'EnableHardwareAcceleratedVideoDecoder': False} if mode == 'cpu'
                else {'RequireHardwareAcceleratedVideoDecoder': True}), 'unchanged original requirement')
        require(dep['forwarded_specification'] == ({'EnableHardwareAcceleratedVideoDecoder': False} if mode == 'cpu'
                else {'RequireHardwareAcceleratedVideoDecoder': True, 'EnableHardwareAcceleratedVideoDecoder': True}), 'forwarded requirement')
        actual = [e for e in dep['events'] if not e['synthetic_control']]
        require([e['key'] for e in actual] == ['IOGVACodec', 'IOAVDHEVCDecodeCapabilities'], 'native dependency queries')
        for i, e in enumerate(actual):
            changed = mode == 'hardware' and i == 0
            require(e['registry_ID'] == 4294968458 and e['native_pinned_callsite']
                    and not e['original_result_present'] and e['return_value_changed'] == changed
                    and e['result_present'] == changed and not e['truncated'], 'pinned IORegistry scope')
        trace = result['trace']
        require(trace['recorders_drained'] and not trace['pending'] and not trace['dropped']
                and meta['status'] == 'COMPLETE' and meta['recorders_drained'] and not meta['pending']
                and not meta['dropped'] and all(not e['truncated'] for e in meta['events']), 'entry/metadata completeness')
        require(len(correlate(trace, meta)) + 1 == len(meta['events']) == meta['calls'], 'metadata bijection')
        if mode == 'cpu':
            row['frames'], row['pixel_bytes'] = software(root, result)
            expected = ([(0x75626572, 0), (0x53747274, 0), (0x6d656d43, 0)]
                        + [(0x43535044, 0)] * 3 + [(0x44656346, 0)] * 6
                        + [(0x46696e46, -12782)] * 2
                        + [(0x43535044, 0), (0x43707950, 0), (0x496e7661, -12782),
                           (0x46696e46, -12782), (0x78787878, 0)])
            require([(r['opcode'], r['status']) for r in own['exchanges']] == expected,
                    'software native reply sequence, including preserved FinF/Inva errors')
            row['software_nonzero_native_replies'] = 4
        else:
            status = -12913 if choice == 'current-board' else -12906
            require(result['public_decode']['decode']['create_status'] == dep['create_status'] == status
                    and result['public_decode']['output_frames'] == 0
                    and not list((root / 'outputs').glob('vt-frame-*.nv12')), 'hardware refusal remains explicit')
            require([r['status'] for r in own['exchanges']] == [0, status], 'actual native Strt reply')
            errors = [(e['caller_offset'], signed32(e['raw_integer_arguments'][2]))
                      for e in trace['events'] if e['index'] == 0]
            expected = ([(4275288, -12900)] if choice == 'current-board' else []) + [(6290187, -12906), (20163, status)]
            require(errors == expected, 'observed error sites/statuses')
            row.update(create_status=status, error_sites=[dict(offset=a, status=b) for a, b in errors])
    if version >= 5:
        calls = (3 if choice == 'current-board' else 1) if mode == 'hardware' else 0
        require(f['policy_choice'] == choice and f['policy_calls'] == len(f['policy_events']) == calls
                and f['policy_substitutions'] == (calls if choice != 'observe' else 0)
                and not f['policy_system_file_modified'], 'policy counts')
        for i, e in enumerate(f['policy_events']):
            require(e['ordinal'] == i and e['caller_offset'] == 722786 and e['key_is_System_Support']
                    and e['original_matches_installed_support'] and e['original_board_missing']
                    and e['return_value_changed'] == (choice != 'observe')
                    and e['returned_board_present'] == (choice == 'current-board')
                    and e['returned_original_pointer'] == (choice == 'observe')
                    and e['replacement_has_process_lifetime_owner'] == (choice != 'observe')
                    and e['borrowed_return_contract'] and not e['original_dictionary_modified'], 'causal policy control')
        row.update(policy_calls=calls, policy_substitutions=f['policy_substitutions'])
    return row


def audit(bridge):
    bridge = bridge.resolve(); results = bridge / 'results'
    rows = []
    for version, build_suffix, prefix in [(1, '', ''), (3, '-03', '-v3'), (4, '-04', '-v4')]:
        build = results / ('video-factory-resolver-build-20261018' + build_suffix)
        for mode, suffix in [('inspect', 'inspect'), ('cpu', 'local-cpu'), ('hardware', 'local-hw-present')]:
            root = results / ('video-factory-resolver' + prefix + '-' + suffix + '-20261018')
            rows.append(case(root, build, bridge, version, mode))
    build = results / 'video-factory-resolver-build-20261018-05'
    v5 = [('inspect', 'inspect', 'observe'), ('local-cpu', 'cpu', 'observe'),
          ('local-hw-observe', 'hardware', 'observe'), ('local-hw-wrong-board', 'hardware', 'wrong-board'),
          ('local-hw-current-board', 'hardware', 'current-board'),
          ('local-hw-current-board-02', 'hardware', 'current-board'),
          ('local-hw-wrong-board-02', 'hardware', 'wrong-board'),
          ('local-hw-current-board-03', 'hardware', 'current-board'),
          ('local-hw-observe-02', 'hardware', 'observe'), ('local-cpu-post', 'cpu', 'observe')]
    for suffix, mode, choice in v5:
        rows.append(case(results / ('video-factory-resolver-v5-' + suffix + '-20261018'), build, bridge, 5, mode, choice))
    rows.sort(key=lambda r: r['started_at'])
    for a, b in zip(rows, rows[1:]):
        require(a['completed_at'] <= b['started_at'], 'overlapping host cohorts')
    policy_cases = [r for r in rows if r['version'] == 5 and r['mode'] == 'hardware']
    require(len({r['original_binary_SHA256'] for r in policy_cases}) == 1, 'policy comparison changed executable')
    failed = results / 'video-factory-resolver-build-20261018-02'
    commands = load(failed / 'commands.json')
    require(len(commands) == 1 and commands[0]['label'] == 'resolver-library' and commands[0]['exit_code'] == 1
            and not (failed / 'inputs.json').exists()
            and b'FigRegistryItemGetFactory' in (failed / 'resolver-library.stderr').read_bytes(), 'preserved link failure')
    baseline = load(results / 'video-local-xpc-progress-20261018/start.json')
    for r in baseline['system_before']:
        require(sha(r['path']) == r['SHA256'], 'protected component changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == baseline['OCLP_SHA256']
            and sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == baseline['policy_SHA256'], 'OCLP/AppleVA policy')
    require(sha(GVA_POLICY) == GVA_POLICY_SHA, 'AppleGVA policy changed')
    support = plistlib.loads(Path(GVA_POLICY).read_bytes())['System Support']
    require('Mac-F2268DAE' not in support and 'iMac11,1' not in support
            and isinstance(support['Mac-27ADBB7B4CEE8E61'], dict), 'original GVA policy state')
    runtime = results / 'native-allocation-runtime-build-20261016-04'
    manifest = load(runtime / 'manifest.json')
    for name, digest in manifest['source_SHA256'].items():
        require(sha(runtime / name) == sha(bridge / name) == digest, 'common runtime source changed')
    require(sha(runtime / 'libKeplerMetal.a') == baseline['shared_runtime_archive_SHA256'], 'common runtime archive changed')
    return dict(status='PASS', scope='Recorded factory/policy cohort; auditor executes no vendor/GPU program',
                native_hosts=len(rows), terminal_nonoverlapping=True, software_images=sum(r['frames'] for r in rows),
                exact_CPU_pixel_bytes=sum(r['pixel_bytes'] for r in rows),
                resolver_mock_controls=sum(r['resolver_controls'] for r in rows),
                GetFactory_mock_controls=sum(r['GetFactory_controls'] for r in rows),
                software_nonzero_native_replies=sum(r['software_nonzero_native_replies'] for r in rows),
                policy_same_binary_hardware_cases=len(policy_cases), current_board_cases=3,
                unchanged_policy_controls=2, wrong_board_controls=2, hardware_images=0,
                failed_builds_preserved=1, failed_native_hosts=0, cases=rows,
                protected_files_unchanged=len(baseline['system_before']), common_sources_unchanged=len(manifest['source_SHA256']),
                OCLP_unchanged=True, AppleVA_policy_unchanged=True, AppleGVA_policy_unchanged=True,
                common_archive_unchanged=True, system_modified=False, hardware_video_execution_proved=False,
                performance_benchmark=False, full_objective_complete=False,
                limits=['Natural GetFactory forwarding changes its immediate caller return address.',
                        'All five software cases retain three FinF and one Inva reply at-12782 each; full service lifetime remains unqualified.',
                        'V1 lacks MH_BUNDLE target metadata; V3 nearest symbol is not an exact factory name.',
                        'The additional property-query error is not established as the final refusal cause.',
                        'An existing board profile is a diagnostic counterfactual, not hardware compatibility proof.',
                        'No decoder method/interface table is directly invoked or patched by the observer.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'new audit output required')
    report = audit(args.lab_root)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
