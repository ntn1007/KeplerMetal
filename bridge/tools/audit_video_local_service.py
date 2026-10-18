#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit historical own-process native video experiments without executing them.

Pixels, raw catalogues and a crash report stay private. Software correctness,
native transport, hardware refusal and failed qualification remain distinct.
"""
from collections import Counter
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import struct
import subprocess

from audit_video_registry import correlate
from audit_video_local_xpc import audit as public_xpc_audit
from audit_video_routing import dictionary_summary, scalar
from native_video_local_service import verify_parent
from verify_native_control_reserve import terminal


def require(value, message):
    if not value:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1024*1024), b''):
            h.update(part)
    return h.hexdigest()


def receipt(root, build, bridge, failed_exit=None):
    inp, frozen = load(root / 'inputs.json'), load(build / 'inputs.json')
    manifest = load(root / 'execution/manifest.json')
    if failed_exit is None:
        terminal(root, bridge, build)
    else:
        require(manifest['exit_code'] == failed_exit and not manifest['SIGKILL_requested']
                and not manifest['authoritative_ps_status'] and manifest['GPU_reservation']['state'] == 'terminal', 'exact failed manifest')
        require(not (root / 'results.json').exists() and not (root / 'execution/execution.stdout').read_bytes(), 'failed process lacks a complete result')
    require(Path(manifest['reservation_root']) == bridge, 'shared lease')
    now = subprocess.run(['ps', '-p', str(manifest['pid']), '-o', 'stat='], text=True, capture_output=True)
    require(not now.stdout.strip(), 'historical PID exists; identity recheck required')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in frozen[key].items():
            require(sha(build / folder / name) == digest, 'frozen build: ' + name)
    require(inp['source_hashes'] == frozen['source_hashes'] and inp['runtime_SHA256'] == frozen['runtime_SHA256'], 'run/build source identity')
    for name, digest in inp['source_hashes'].items():
        require(sha(root / name) == digest, 'run source: ' + name)
    for name, digest in inp['assets_SHA256'].items():
        require(sha(root / 'assets' / name) == digest, 'run asset: ' + name)
    for name in frozen['assets_SHA256']:
        if name not in ('owned-choice.json', 'dependency-choice.json'):
            require(inp['assets_SHA256'][name] == frozen['assets_SHA256'][name], 'invariant asset')
    require(sha(root / 'application') == sha(build / 'application') == frozen['executable_SHA256']
            == inp['executable_SHA256'] == manifest['original_binary_sha256']
            and sha(root / 'execution/application') == manifest['signed_binary_sha256'], 'executable identity')
    for path, digest in frozen['reused_objects_and_libraries_SHA256'].items():
        require(sha(path) == digest, 'qualified prerequisite')
    parent = Path(frozen['parent_build'])
    require(sha(parent / 'inputs.json') == frozen['parent_inputs_SHA256'], 'parent manifest')
    verify_parent(parent)
    require(sha(build / 'libVideoOwned.dylib') == frozen['library_SHA256']
            and sha(build / 'main.o') == frozen['new_main_object_SHA256'], 'new library/main object')
    if 'metadata_library_SHA256' in frozen:
        require(sha(build / 'libVideoRegistryMetadata.dylib') == frozen['metadata_library_SHA256']
                == load(root / 'assets/registry-config.json')['metadata_library_SHA256']
                and frozen['metadata_capacity'] == 512, 'bounded metadata rebuild')
    require(all(c['exit_code'] == 0 for c in load(build / 'commands.json')), 'build commands')
    require(manifest['arguments'] == [str(root / 'assets'), str(root / 'outputs'), inp['mode']], 'actual arguments')
    return inp, manifest


def owned(data, manifest, expected):
    require(data['status'] == 'COMPLETE' and data['preflight'] and data['recorders_drained']
            and data['unexpected'] == 0 and data['PID'] == manifest['pid'], 'owned transport completeness')
    require(data['constructor_calls'] == data['accepted'] == data['native_callback_returned'] == int(expected)
            and data['constructor_return_replaced'] == expected, 'native callback/constructor counts')
    require(data['native_handler_offset'] == 4268444 and data['native_handler_bytes'] == 101
            and data['native_handler_SHA256'] == '100deacc2722bfbba2cee35dcf2ddcd00628d9840991e9d6f2ff82d426cab3b9', 'resident callback profile')
    for key in ['system_service_modified', 'system_modified', 'hardware_video_execution_proved',
                'performance_benchmark', 'message_contents_modified', 'native_event_handlers_replaced',
                'full_native_service_lifetime_qualified']:
        require(data[key] is False, 'scope: ' + key)
    if expected:
        require(data['client_peer_PID'] == manifest['pid'] and len(data['exchanges']) >= 2, 'same-process peer')
        for row in data['exchanges']:
            require(row['peer_PID'] == manifest['pid'] and row['same_process'] and row['has_opcode']
                    and row['has_status'] and row['reply_is_dictionary']
                    and not row['reply_connection_invalid'] and not row['reply_connection_interrupted'], 'unchanged native replies')
        require([r['opcode'] for r in data['exchanges'][:2]] == [1969382770, 1400140404], 'actual initial protocol')
    else:
        require(not data['exchanges'] and data['client_peer_PID'] == 0, 'no owned exchanges')


def software(root, result):
    decode = result['public_decode']; call = decode['decode']
    require(decode['fixture_samples'] == decode['output_frames'] == 6
            and decode['format_create_status'] == call['create_status'] == 0
            and call['decode_status'] == [0]*6 and call['finish_status'] == call['wait_status'] == 0
            and decode['different_bytes'] == decode['missing_CPU_references'] == 0
            and decode['CPU_reference_bytes_compared'] == 691200, 'software decode results')
    require(len(decode['frame_files']) == 6, 'software frame count')
    for i, name in enumerate(decode['frame_files']):
        require(name == 'vt-frame-%03d.nv12' % i, 'frame path')
        raw = (root / 'outputs' / name).read_bytes()
        ref = (root / 'assets/fixtures/H264' / ('cpu-frame-%03d.nv12' % i)).read_bytes()
        require(len(raw) == 115200 and raw == ref, 'independent CPU pixel bytes')
    return 6, 691200


def dependency(root, mode, choice, incomplete=False):
    dep = load(root / ('outputs/dependency.json' if incomplete else 'dependency.json'))
    require(dep['status'] == 'COMPLETE' and dep['recorders_drained'] and not dep['dropped'] and not dep['pending']
            and dep['public_query_controls_valid'] and dep['public_create_called']
            and dep['hardware_requirement_preserved'] and not dep['system_modified'], 'dependency observer')
    require(dep['counterfactual_selection'] == choice, 'dependency selection')
    if mode == 'cpu':
        require(dep['original_specification'] == dep['forwarded_specification']
                == {'EnableHardwareAcceleratedVideoDecoder': False} and not dep['both_flags_applied'], 'original software requirement')
    else:
        require(dep['original_specification'] == {'RequireHardwareAcceleratedVideoDecoder': True}
                and dep['forwarded_specification'] == {'RequireHardwareAcceleratedVideoDecoder': True,
                                                     'EnableHardwareAcceleratedVideoDecoder': True}
                and dep['both_flags_applied'] and dep['create_status'] == -12906, 'original strict hardware requirement/refusal')
    events = [e for e in dep['events'] if not e['synthetic_control']]
    expected = ['IOGVACodec', 'IOAVDHEVCDecodeCapabilities'] if mode == 'hardware' or load(root / 'inputs.json')['route'] == 'owned' else []
    require([e['key'] for e in events] == expected, 'observed native queries: ' + root.name)
    for i, row in enumerate(events):
        changed = mode == 'hardware' and choice == 'present-key' and i == 0
        require(row['registry_ID'] == 4294968458 and row['registry_ID_status'] == 0
                and row['name'] == row['class'] == 'nvAccelerator'
                and row['plane'] == 'IOService' and row['options'] == 1 and row['native_pinned_callsite']
                and not row['original_result_present'] and row['return_value_changed'] == changed
                and row['result_present'] == changed and not row['truncated'], 'exact presence scope')
    require(dep['substitutions'] == int(mode == 'hardware' and choice == 'present-key'), 'substitution count')
    return dep


def successful_case(root, build, bridge, mode, route, choice):
    inp, manifest = receipt(root, build, bridge)
    require(inp['mode'] == mode and inp['route'] == route
            and load(root / 'assets/owned-choice.json') == {'route': route}, 'route selection')
    result, own = load(root / 'results.json'), load(root / 'owned.json')
    reached = route == 'owned' and (mode == 'cpu' or choice == 'present-key')
    owned(own, manifest, reached)
    row = {'case': root.name, 'qualification_status': 'PASS', 'mode': mode, 'route': route,
           'choice': choice, 'PID': manifest['pid'], 'manifest_SHA256': sha(root / 'execution/manifest.json'),
           'results_SHA256': sha(root / 'results.json'), 'owned_SHA256': sha(root / 'owned.json'),
           'callback_returned': own['native_callback_returned'], 'frames': 0, 'pixel_bytes': 0,
           'entry_calls': 0, 'metadata_associations': 0, 'owned_sync_replies': len(own['exchanges']),
           'started_at': manifest['started_at'], 'completed_at': manifest['completed_at']}
    if mode == 'inspect':
        require(result['public_decode'] is None, 'inspect ran decoder')
        return row
    dep = dependency(root, mode, choice)
    trace, meta = result['trace'], load(root / 'metadata.json')
    require(trace['recorders_drained'] and not trace['pending'] and not trace['dropped']
            and meta['status'] == 'COMPLETE' and meta['recorders_drained'] and not meta['pending'] and not meta['dropped']
            and all(not e['truncated'] for e in meta['events']), 'complete entry/metadata capture')
    pairs = correlate(trace, meta)
    require(len(pairs)+1 == len(meta['events']) == meta['calls'], 'complete metadata association')
    row.update(entry_calls=trace['calls'], metadata_associations=len(pairs),
               create_status=dep['create_status'], substitutions=dep['substitutions'])
    if mode == 'cpu':
        row['frames'], row['pixel_bytes'] = software(root, result)
        if reached:
            require([r['status'] for r in own['exchanges'][:2]] == [0, 0], 'software native transport success')
    else:
        require(result['public_decode']['decode']['create_status'] == -12906
                and result['public_decode']['output_frames'] == 0
                and not list((root / 'outputs').glob('vt-frame-*.nv12')), 'hardware refusal preserved')
        if reached:
            require([r['status'] for r in own['exchanges']] == [0, -12906], 'local native Strt refusal')
            selected = [obj for raw, obj in pairs if raw['index'] == 3 and raw['caller_offset'] == 6289206]
            require(len(selected) == 2 and all('com.apple.videotoolbox.videodecoder.h264.gva' in r['description'] for r in selected), 'both GVA selections observed')
            images = load(root / 'images.json')['after']['images']
            gva = [r for r in images if r['alive'] and r['path'] == '/System/Library/PrivateFrameworks/AppleGVA.framework/Versions/A/AppleGVA']
            require(len(gva) == 1 and gva[0]['UUID'] == 'ca5414f369373c059ea2d82b35afd4f0'
                    and gva[0]['current_version'] == '10.0.20' and gva[0]['header_metadata_valid'], 'actual AppleGVA load')
            row.update(GVA_candidates_observed=2, native_factory_entry_calls=trace['counts']['FigRegistryItemGetFactory'],
                       AppleGVA_UUID=gva[0]['UUID'], AppleGVA_version=gva[0]['current_version'])
    return row


def failed_cases(results, bridge):
    rows = []
    for version, code in [(2, -11), (3, 6)]:
        root = results / ('video-owned-service-v%d-local-hw-present-20261018' % version)
        build = results / ('video-owned-service-build-20261018-0%d' % version)
        inp, manifest = receipt(root, build, bridge, code)
        require(inp['mode'] == 'hardware' and inp['route'] == 'owned', 'failed case scope')
        dependency(root, 'hardware', 'present-key', incomplete=True)
        meta = load(root / 'outputs/metadata.json')
        require(meta['status'] == 'INCOMPLETE' and meta['calls'] == 269
                and len(meta['events']) == 256 and meta['dropped'] == 13 and not meta['pending'], 'preserved truncated metadata')
        require(not list((root / 'outputs').glob('vt-frame-*.nv12')), 'failure created image')
        if version == 2:
            require(not (root / 'outputs/owned.json').exists(), 'crash completed snapshot unexpectedly')
            private = results / 'video-local-xpc-progress-20261018/native-hw-failure'
            record = load(private / 'receipt.json')
            require(sha(private / 'crash-report.private.ips') == record['report_SHA256']
                    and record['PID'] == manifest['pid'] == 42582
                    and record['termination']['code'] == 11, 'actual crash receipt')
        else:
            owned(load(root / 'outputs/owned.json'), manifest, True)
            require(not (root / 'execution/execution.stderr').read_bytes(), 'unexpected watchdog/error marker')
        rows.append({'case': root.name, 'qualification_status': 'FAIL_PRESERVED', 'PID': manifest['pid'],
                     'exit_code': code, 'cause': 'native client cleanup crash' if version == 2 else 'metadata capacity guard',
                     'metadata_dropped': 13, 'manifest_SHA256': sha(root / 'execution/manifest.json'),
                     'started_at': manifest['started_at'], 'completed_at': manifest['completed_at']})
    return rows


def audit(lab):
    bridge = lab.resolve() / 'bridge'; results = bridge / 'results'
    rows = []; frames = pixels = local_frames = 0
    cohorts = {
        1: [('inspect', 'inspect', 'native', 'native'), ('native-cpu', 'cpu', 'native', 'native'), ('local-cpu', 'cpu', 'owned', 'native')],
        2: [('inspect', 'inspect', 'native', 'native'), ('native-cpu', 'cpu', 'native', 'native'), ('local-cpu', 'cpu', 'owned', 'native'),
            ('local-hw-native', 'hardware', 'owned', 'native'), ('local-hw-wrong', 'hardware', 'owned', 'wrong-key')],
        3: [('inspect', 'inspect', 'native', 'native'), ('local-cpu', 'cpu', 'owned', 'native')],
        4: [('inspect', 'inspect', 'native', 'native'), ('native-cpu', 'cpu', 'native', 'native'), ('local-cpu', 'cpu', 'owned', 'native'),
            ('local-hw-native', 'hardware', 'owned', 'native'), ('local-hw-wrong', 'hardware', 'owned', 'wrong-key'),
            ('local-hw-present', 'hardware', 'owned', 'present-key'), ('native-hw-present', 'hardware', 'native', 'present-key')]}
    for version, cases in cohorts.items():
        build = results / ('video-owned-service-build-20261018' + ('-0%d' % version if version > 1 else ''))
        for name, mode, route, choice in cases:
            prefix = 'video-owned-service-' + ('v%d-' % version if version > 1 else '')
            row = successful_case(results / (prefix + name + '-20261018'), build, bridge, mode, route, choice)
            rows.append(row); frames += row['frames']; pixels += row['pixel_bytes']
            if route == 'owned': local_frames += row['frames']
    rows += failed_cases(results, bridge)
    public = public_xpc_audit(lab)
    # Constructor-only observation extends schema3, preserving old hosts.
    constructors = []
    build = results / 'video-xpc-constructors-build-20261018'
    for mode in ['inspect', 'cpu']:
        root = results / ('video-xpc-constructors-%s-20261018' % mode)
        terminal(root, bridge, build)
        manifest, route = load(root / 'execution/manifest.json'), load(root / 'routing.json')
        require(route['schema'] == 4 and route['synthetic_controls_valid'] and route['synthetic_ABI_calls'] == 112
                and route['named_constructor_control_calls'] == 16
                and len(route['named_constructor_controls']) == 16
                and all(r['correct'] and r['errno_preserved'] for r in route['named_constructor_controls']), 'named constructor controls')
        native = [r for r in route['events'] if not r['synthetic_control']]
        for event in native:
            dictionary_summary(event['message']); dictionary_summary(event['reply'])
        selected = [r for r in native if r['API'] == 'create' and r['service'] == 'com.apple.coremedia.videodecoder']
        require(len(selected) == int(mode == 'cpu') and all(r['caller']['caller_offset'] == 6326308 for r in selected), 'actual constructor site')
        if mode == 'cpu':
            n, size = software(root, load(root / 'results.json')); frames += n; pixels += size
        constructors.append({'case': root.name, 'PID': manifest['pid'], 'started_at': manifest['started_at'],
                             'completed_at': manifest['completed_at'], 'manifest_SHA256': sha(root / 'execution/manifest.json')})
    all_rows = rows + public['cases'] + constructors
    ordered = sorted(all_rows, key=lambda r: r['started_at'])
    for a, b in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(a['completed_at']) <= datetime.datetime.fromisoformat(b['started_at']), 'overlapping experimental hosts')
    require(len(all_rows) == len({r['PID'] for r in all_rows}) == 33, 'fresh host count')
    return {'status': 'AUDIT_PASS_WITH_FOUR_PRESERVED_QUALIFICATION_FAILURES', 'terminal_hosts': 33,
            'nonoverlapping': True, 'owned_native_hosts': len(rows), 'public_XPC_hosts': public['terminal_processes'],
            'constructor_observer_hosts': len(constructors), 'preserved_failed_hosts': 4,
            'CPU_images': frames, 'CPU_exact_pixel_bytes': pixels, 'owned_transport_CPU_images': local_frames,
            'public_XPC_exact_uint32_words': public['exact_uint32_words'], 'public_XPC_primer_words': public['primer_words'],
            'hardware_completed_refusals': sum(r.get('mode') == 'hardware' for r in rows),
            'hardware_execution_proved': False, 'full_objective_complete': False,
            'native_factory_actual_return_observed': False, 'hardware_refusal_root_cause_proved': False,
            'new_M1_execution': False, 'Qwen_job_ids': [], 'system_modified': False, 'performance_benchmark': False,
            'processes': rows, 'constructor_processes': constructors, 'public_XPC_audit_SHA256':
            sha(results / 'video-local-xpc-progress-20261018/public-audit.json')}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--lab-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    require(not args.out.exists(), 'new output required')
    result = audit(args.lab_root); result['auditor_SHA256'] = sha(__file__)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('processes', 'constructor_processes')}))


if __name__ == '__main__':
    main()
