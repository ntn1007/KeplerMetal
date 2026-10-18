#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit recorded own-process public-XPC observations without native execution.

The report publishes scalar protocol observations, hashes and scoped failures.
Raw IPC catalogues, object descriptions, addresses and pixels stay in the lab.
An observed service name does not identify its running executable or modules.
"""
from collections import Counter
from pathlib import Path
import argparse
import datetime
import difflib
import hashlib
import json
import plistlib

from audit_video_registry import correlate
from native_video_routing import verify_base
from verify_native_control_reserve import terminal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


SCALAR_KEYS = {'status', 'err', 'error', 'osstatus', 'errorcode', 'errorreturn',
               'opcode', 'operation', 'messageid', 'method'}
SERVICE = 'com.apple.coremedia.videodecoder'


def dictionary_summary(data):
    if not data:
        return
    require(set(data) <= {'type', 'keys', 'key_count', 'truncated',
                         'binary_or_string_values_copied', 'error_kind'}, 'unexpected object payload')
    if data['type'] != 'dictionary':
        require('keys' not in data, 'nested object payload')
        return
    require(data['binary_or_string_values_copied'] is False and not data['truncated']
            and len(data['keys']) == data['key_count'] <= 32, 'dictionary coverage')
    require([e['key'] for e in data['keys']] == sorted(e['key'] for e in data['keys']), 'key ordering')
    for item in data['keys']:
        require(set(item) <= {'key', 'type', 'scalar', 'scalar_signed32', 'scalar_omitted',
                             'scalar_encoding'} and len(item['key'].encode()) <= 256, 'unexpected key payload')
        if any(k in item for k in ('scalar', 'scalar_signed32', 'scalar_omitted')):
            require(item['key'].lower().removeprefix('.') in SCALAR_KEYS, 'non-allowlisted scalar')
        if 'scalar' in item:
            require(type(item['scalar']) is int and -(2**31) <= item['scalar'] < 2**32
                    and item['type'] in ('int64', 'uint64'), 'unbounded scalar')
        if 'scalar_signed32' in item:
            require(type(item['scalar_signed32']) is int and -(2**31) <= item['scalar_signed32'] < 0
                    and item['scalar_encoding'] == 'uint64_sign_extended_int32'
                    and item['type'] == 'uint64' and 'scalar' not in item, 'invalid signed status encoding')


def scalar(data, key):
    found = [e for e in data.get('keys', []) if e['key'] == key]
    require(len(found) == 1, 'missing or ambiguous protocol field: ' + key)
    return found[0].get('scalar', found[0].get('scalar_signed32'))


def audit(lab):
    lab = lab.resolve()
    results = lab / 'results'
    progress = results / 'video-routing-progress-20261018'
    builds = [results / 'video-routing-build-20261018', results / 'video-routing-build-20261018-02']
    frozen = []
    for build in builds:
        data = load(build / 'inputs.json')
        for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
            for name, digest in data[key].items():
                require(sha(build / folder / name) == digest, 'frozen build input: ' + name)
        require(len(load(build / 'commands.json')) == 6
                and all(c['exit_code'] == 0 for c in load(build / 'commands.json')), 'build completion')
        for name, digest in data['new_object_SHA256'].items():
            require(sha(build / name) == digest, 'new object identity')
        for codec, digest in data['executable_variants_SHA256'].items():
            require(sha(build / ('application-' + codec)) == digest, 'binary identity')
        base = Path(data['dependency_build'])
        require(data['dependency_inputs_SHA256'] == sha(base / 'inputs.json'), 'dependency version')
        verify_base(base)
        require(sha(build / 'video_registry_client.mm') == data['qualified_host_source_SHA256']
                == sha(base / 'video_registry_client.mm') and data['qualified_host_source_unchanged']
                and not data['qualified_host_object_reused'] and data['catalog_and_decoder_objects_reused'], 'host source/object boundary')
        require(sha(build / 'libVideoRouting.dylib') == data['routing_library_SHA256']
                and not data['GPU_execution'] and not data['unknown_private_function_invoked_by_host'], 'build scope')
        frozen.append(data)
    patch = lab.parent / 'patches/video-routing-v1-to-v2.patch'
    expected = ''.join(difflib.unified_diff((builds[0] / 'video_routing.mm').read_text().splitlines(True),
        (builds[1] / 'video_routing.mm').read_text().splitlines(True),
        fromfile='a/bridge/tools/video_routing.mm', tofile='b/bridge/tools/video_routing.mm'))
    require(patch.read_text() == expected, 'own source version reconstruction patch')
    reconstruction = load(progress / 'source-reconstruction.json')
    require(reconstruction['status'] == 'PASS' and reconstruction['patch_SHA256'] == sha(patch)
            and reconstruction['reconstructed_v1_SHA256'] == sha(builds[0] / 'video_routing.mm')
            == sha(progress / 'reconstructed-v1/bridge/tools/video_routing.mm'), 'independent reverse patch')
    profile = load(progress / 'routing-profile.json')
    modules = {m['install_name']: m for m in profile['modules']}
    require(len(modules) == 7 and len(profile['required_before_begin']) == 3, 'public API caller profile')
    require(frozen[0]['qualified_host_source_SHA256'] == frozen[1]['qualified_host_source_SHA256'], 'qualified host changed across logger versions')
    rows, manifests, balanced = [], [], []
    counts = Counter()
    version1 = [('video-routing-inspect-20261018', 'H264', 'inspect', 'native', 'observe'),
                ('video-routing-H264-cpu-20261018', 'H264', 'cpu', 'native', 'observe'),
                ('video-routing-H264-native-20261018', 'H264', 'hardware', 'native', 'observe'),
                ('video-routing-H264-present-20261018', 'H264', 'hardware', 'present-key', 'observe')]
    version2 = [('video-routing-v2-inspect-20261018', 'H264', 'inspect', 'native', 'observe'),
                ('video-routing-v2-H264-cpu-20261018', 'H264', 'cpu', 'native', 'observe'),
                ('video-routing-v2-MPEG2Video-cpu-20261018', 'MPEG2Video', 'cpu', 'native', 'observe'),
                ('video-routing-v2-MPEG2Video-hardware-20261018', 'MPEG2Video', 'hardware', 'native', 'observe'),
                ('video-routing-v2-H264-present-passive-20261018', 'H264', 'hardware', 'present-key', 'passive')]
    orders = [('native', 'wrong-key', 'present-key'), ('present-key', 'native', 'wrong-key'),
              ('wrong-key', 'present-key', 'native')]
    balanced_names = {'video-routing-v2-' + choice + '-r' + str(repeat) + '-20261018'
                      for repeat, order in enumerate(orders, 1) for choice in order}
    for repeat, order in enumerate(orders, 1):
        version2.extend(('video-routing-v2-' + choice + '-r' + str(repeat) + '-20261018',
                         'H264', 'hardware', choice, 'observe') for choice in order)
    version2.append(('video-routing-v2-H264-cpu-after-20261018', 'H264', 'cpu', 'native', 'observe'))
    for version, cases in enumerate((version1, version2)):
        build, fi = builds[version], frozen[version]
        for name, codec, mode, choice, capture in cases:
            root = results / name
            run = terminal(root, lab, build)
            require(sha(root / 'runner.py') == sha(build / 'builder.py'), 'executed runner source')
            for key, value in fi.items():
                if key != 'assets_SHA256':
                    require(run[key] == value, 'run/build provenance: ' + key)
            require(run['executable_SHA256'] == fi['executable_variants_SHA256'][codec]
                    and run['selected_codec'] == codec and run['override_mode'] == choice
                    and run['routing_mode'] == capture, 'run selection')
            require(set(run['assets_SHA256']) == set(fi['assets_SHA256']), 'asset set changed')
            require(all(run['assets_SHA256'][k] == v for k, v in fi['assets_SHA256'].items()
                        if k not in ('dependency-choice.json', 'routing-choice.json')), 'non-choice asset changed')
            require(load(root / 'assets/dependency-choice.json') == {'mode': choice}
                    and load(root / 'assets/routing-choice.json') == {'mode': capture}, 'explicit choices')
            m = load(root / 'execution/manifest.json')
            require(m['arguments'] == [str(root / 'assets'), str(root / 'outputs'), mode], 'actual host arguments')
            manifests.append(m)
            d, route = load(root / 'results.json'), load(root / 'routing.json')
            require(route == load(root / 'outputs/routing.json') and route['status'] == 'COMPLETE'
                    and route['recorders_drained'] and route['disabled_before_snapshot'] and not route['dropped'], 'incomplete XPC observation')
            require(route['synthetic_controls_valid'] and route['synthetic_ABI_calls'] == 96
                    and len(route['controls']) == 32 and all(c['correct'] and c['callbacks'] == 1 for c in route['controls']), 'ABI mock controls')
            require(route['native_capture_enabled'] == (capture == 'observe') and route['own_process_only'], 'capture selection')
            for key in ('synthetic_native_IPC_calls', 'system_modified', 'arguments_or_return_values_modified',
                        'async_handler_replaced', 'observer_generated_native_messages',
                        'message_binary_or_string_values_copied', 'other_process_injected'):
                require(not route[key], 'XPC scope: ' + key)
            if version:
                require(route['schema'] == 2 and route['scalar_summary_controls_calls'] == 14
                        and len(route['scalar_summary_controls']) == 14
                        and all(c['correct'] for c in route['scalar_summary_controls']), 'bounded summary controls')
                counts['summary_controls'] += 14
            counts['mock_ABI_calls'] += 96
            events = route['events']
            require(route['calls'] == len(events) and [e['ordinal'] for e in events] == list(range(len(events))), 'event count/order')
            mock = [e for e in events if e['synthetic_control']]
            require(len(mock) == 96, 'mock event count')
            for i in range(32):
                create, sync, async_ = mock[3*i:3*i+3]
                require([e['API'] for e in (create, sync, async_)] == ['create_mach_service', 'send_with_reply_sync', 'send_with_reply']
                        and create['flags'] == 2**63 + i * 0x100000001 and create['result_present']
                        and sync['result_present'] and not async_['result_present']
                        and scalar(sync['message'], 'opcode') == i and scalar(sync['reply'], 'status') == -100-i
                        and scalar(async_['message'], 'opcode') == i, 'mock forwarding evidence')
            native = [e for e in events if not e['synthetic_control']]
            counts['native_XPC_records'] += len(native)
            for event in events:
                require(not event['truncated'], 'truncated service name')
                dictionary_summary(event['message'])
                dictionary_summary(event['reply'])
                if not event['synthetic_control']:
                    expected_module = modules.get(event['caller']['install_name'])
                    require(expected_module and all(event['caller'][k] == expected_module[k]
                            for k in ('UUID', 'current_version')), 'native caller identity')
            if capture == 'passive' or mode == 'inspect':
                require(not native, 'passive/inspect native observation')
            decoder = [e for e in native if e['service'] == SERVICE]
            first = [e for e in decoder if e['caller']['caller_offset'] == 6326974]
            second = [e for e in decoder if e['caller']['caller_offset'] == 6327491]
            reached = mode == 'cpu' or (choice == 'present-key' and capture == 'observe')
            require(bool(decoder) == reached, 'decoder route distinction')
            if reached:
                require(len(first) == len(second) == 1
                        and all(e['API'] == 'send_with_reply_sync' for e in decoder)
                        and scalar(first[0]['message'], 'OpCode') == scalar(first[0]['reply'], 'OpCode') == 1969382770
                        and scalar(first[0]['reply'], 'Status') == 0
                        and scalar(second[0]['message'], 'OpCode') == scalar(second[0]['reply'], 'OpCode') == 1400140404, 'actual public-XPC exchange')
                if mode == 'cpu':
                    require(scalar(second[0]['reply'], 'Status') == 0, 'software startup status')
                elif version:
                    require(len(decoder) == 2 and scalar(second[0]['reply'], 'Status') == -12906, 'service startup refusal')
                    counts['hardware_startup_status_observed'] += 1
                else:
                    require(next(e for e in second[0]['reply']['keys'] if e['key'] == 'Status')['scalar_omitted'], 'v1 omitted negative status')
            row = {'case': name, 'logger_schema': version+1, 'codec': codec, 'mode': mode, 'choice': choice,
                'routing': capture, 'result_SHA256': sha(root / 'results.json'), 'routing_SHA256': sha(root / 'routing.json'),
                'inputs_SHA256': sha(root / 'inputs.json'), 'native_XPC_records': len(native),
                'decoder_service_records': len(decoder), 'decoder_route_observed': reached}
            rows.append(row)
            if mode == 'inspect':
                require(not d['public_decode'] and not d['hardware_video_execution_proved'], 'inspect ran decode')
                continue
            for key in ('direct_unknown_private_call', 'system_modified', 'performance_benchmark', 'hardware_video_execution_proved'):
                require(not d[key], 'codec scope: ' + key)
            dep, meta = load(root / 'dependency.json'), load(root / 'metadata.json')
            require(dep == load(root / 'outputs/dependency.json') and meta == load(root / 'outputs/metadata.json'), 'copied evidence mismatch')
            require(dep['status'] == meta['status'] == 'COMPLETE' and dep['recorders_drained']
                    and meta['recorders_drained'] and not dep['pending'] and not meta['pending']
                    and not dep['dropped'] and not meta['dropped'] and dep['public_query_controls_valid']
                    and dep['profile']['scope_contract_valid'] and dep['profile']['GPU_registry_ID'] == 4294968458,
                    'dependency/metadata profile')
            require(not dep['return_ownership_modified'] and dep['hardware_requirement_preserved']
                    and dep['substitutions'] == int(choice == 'present-key'), 'counterfactual boundary')
            real = [e for e in dep['events'] if not e['synthetic_control']]
            require(len(real) == (2 if codec == 'H264' and mode == 'hardware' else 0), 'native property queries')
            require(all(e['native_pinned_callsite'] and e['registry_ID'] == 4294968458 and not e['original_result_present']
                    and e['return_value_changed'] == (choice == 'present-key' and e['key'] == 'IOGVACodec') for e in real), 'query scope')
            counts['real_property_queries'] += len(real)
            counts['public_query_controls'] += 2
            counts['scope_contracts'] += 10
            trace = d['trace']
            require(trace['recorders_drained'] and not trace['pending'] and not trace['dropped']
                    and not trace['arguments_modified'] and not trace['original_instructions_modified'], 'entry observer')
            pairs = correlate(trace, meta)
            require(len(pairs) + 1 == meta['calls'] == len(meta['events']), 'metadata association')
            counts['real_CF_metadata_objects'] += len(pairs)
            decoded = d['public_decode']
            require(decoded['fixture_samples'] == 6 and decoded['format_create_status'] == 0, 'public fixture')
            if mode == 'cpu':
                require(dep['original_specification'] == dep['forwarded_specification']
                        == {'EnableHardwareAcceleratedVideoDecoder': False}
                        and decoded['decode']['create_status'] == 0 and decoded['output_frames'] == 6
                        and decoded['different_bytes'] == decoded['missing_CPU_references'] == 0
                        and decoded['decode']['decode_status'] == [0]*6
                        and decoded['decode']['finish_status'] == decoded['decode']['wait_status'] == 0, 'software decode')
                for i, file in enumerate(decoded['frame_files']):
                    require(file == 'vt-frame-%03d.nv12' % i, 'output filename')
                    actual = (root / 'outputs' / file).read_bytes()
                    ref = (root / 'assets/fixtures' / codec / ('cpu-frame-%03d.nv12' % i)).read_bytes()
                    require(len(actual) == 115200 and actual == ref, 'independent numerical pixels')
                    counts['CPU_images'] += 1
                    counts['CPU_bytes'] += len(actual)
            else:
                require(dep['original_specification'] == {'RequireHardwareAcceleratedVideoDecoder': True}
                        and dep['forwarded_specification'] == ({'RequireHardwareAcceleratedVideoDecoder': True,
                            'EnableHardwareAcceleratedVideoDecoder': True} if codec == 'H264'
                            else {'RequireHardwareAcceleratedVideoDecoder': True}), 'strict hardware request')
                require(decoded['decode']['create_status'] == dep['create_status'] == -12906
                        and decoded['output_frames'] == 0 and not decoded['frame_files']
                        and not list((root / 'outputs').glob('vt-frame-*.nv12')), 'retained hardware failure')
                errors = [e for e in trace['events'] if e['index'] == 0]
                require([e['caller_offset'] for e in errors] == ([6290187, 20163] if choice == 'present-key' else [20163]), 'error return sites')
                require(all(e['raw_integer_arguments'][2] & 0xffffffff == (-12906 & 0xffffffff) for e in errors), 'error register evidence')
                counts['hardware_failures'] += 1
            row.update(create_status=decoded['decode']['create_status'], frames=decoded['output_frames'])
            if name in balanced_names:
                balanced.append({'case': name, 'choice': choice, 'raw_executable_SHA256': run['executable_SHA256'],
                    'signed_executable_SHA256': m['signed_binary_sha256'],
                    'routing_library_SHA256': run['routing_library_SHA256'], 'assets_SHA256': run['assets_SHA256'],
                    'decoder_records': len(decoder), 'service_startup_status': -12906 if reached else None})
    require(len(rows) == 19 and counts['CPU_images'] == 24 and counts['CPU_bytes'] == 2764800
            and counts['hardware_failures'] == 13 and counts['hardware_startup_status_observed'] == 3
            and counts['summary_controls'] == 210 and counts['mock_ABI_calls'] == 1824, 'cohort totals')
    require(len(balanced) == 9 and all(len({r[k] for r in balanced}) == 1 for k in
            ('raw_executable_SHA256', 'signed_executable_SHA256', 'routing_library_SHA256')), 'balanced binary identity')
    invariant = {k: v for k, v in balanced[0]['assets_SHA256'].items() if k != 'dependency-choice.json'}
    require(all({k: v for k, v in r['assets_SHA256'].items() if k != 'dependency-choice.json'} == invariant
                for r in balanced), 'balanced invariant assets')
    for row in balanced:
        del row['assets_SHA256']
    ordered = sorted(manifests, key=lambda m: m['started_at'])
    for a, z in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(a['completed_at']) <= datetime.datetime.fromisoformat(z['started_at']), 'overlapping cooperative native processes')
    actual_order = [Path(m['original_executable']).parent.name for m in ordered
                    if Path(m['original_executable']).parent.name in balanced_names]
    require(actual_order == [r['case'] for r in balanced], 'rotated actual order')
    start = load(progress / 'start.json')
    require(len(start['system_before']) == 83, 'system pin set')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'protected system file changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256'], 'OCLP changed')
    require(sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == start['policy_SHA256'], 'video policy changed')
    runtime = load(results / 'native-allocation-runtime-build-20261016-04/manifest.json')
    require(len(runtime['source_SHA256']) == 36, 'common source inventory')
    for name, digest in runtime['source_SHA256'].items():
        require(sha(lab / name) == digest, 'common runtime source changed')
    bundle = load(progress / 'service-bundle-metadata.json')
    require(bundle['bundle_identifier'] == SERVICE
            and sha(bundle['Info_path']) == bundle['Info_SHA256']
            and sha(bundle['executable_path']) == bundle['executable_SHA256']
            and plistlib.loads(Path(bundle['Info_path']).read_bytes())['CFBundleIdentifier'] == SERVICE
            and not bundle['native_invocation'] and not bundle['remote_process_inspected']
            and not bundle['system_modified'], 'static bundle identity')
    return {'status': 'PASS', 'auditor_SHA256': sha(__file__), 'native_processes_terminal': 19,
        'nonoverlapping_cooperative_host_runs': True, 'logger_v1_processes': 4, 'logger_v2_processes': 15,
        'counts': dict(counts), 'CPU_different_bytes': 0, 'hardware_create_status': -12906,
        'decoder_service': SERVICE, 'uber_opcode': 1969382770, 'Strt_opcode': 1400140404,
        'uber_return_offset': 6326974, 'Strt_return_offset': 6327491,
        'positive_service_uber_status': 0, 'positive_service_Strt_status': -12906,
        'negative_decoder_exchanges_observed': 0, 'signed_status_v1_omitted': True,
        'source_version_patch_SHA256': sha(patch), 'counterfactual': balanced,
        'v1_source_reconstruction_verified': True,
        'static_matching_service_bundle': {k: bundle[k] for k in ('bundle_identifier', 'Info_SHA256', 'executable_SHA256')},
        'qualified_host_source_unchanged': True, 'qualified_host_object_reused': False,
        'qualified_decoder_catalogue_and_dependency_libraries_reused': True,
        'remote_executable_or_loaded_modules_identified': False, 'remote_registry_state_observed': False,
        'single_complete_root_cause_established': False, 'native_async_reply_callbacks_observed': False,
        'hardware_video_execution_proved': False, 'full_objective_complete': False,
        'system_files_unchanged': 83, 'additional_video_policy_unchanged': True, 'OCLP_unchanged': True,
        'common_runtime_sources_unchanged': 36, 'performance_benchmark': 'NOT RUN',
        'system_deployment': 'NOT RUN', 'new_M1_execution': False, 'Qwen_job_ids': [], 'processes': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Audit destination exists')
    report = audit(args.lab_root)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'native_processes_terminal', 'counts',
        'positive_service_Strt_status', 'hardware_video_execution_proved')}))


if __name__ == '__main__':
    main()
