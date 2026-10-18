#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck recorded public peer metadata without launching native/GPU work.

PID/birth/path consistency is corroborated by bounded server logs and its
installed Mach-O UUID. This is not cryptographic peer authentication and does
not inspect another process's memory or certify a hardware video decoder.
"""
from collections import Counter
from pathlib import Path
import argparse
import datetime
import difflib
import hashlib
import json
import re

from audit_video_registry import correlate
from audit_video_routing import dictionary_summary, scalar, SERVICE
from native_video_routing import verify_base
from verify_native_control_reserve import terminal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def static_entry(results):
    """Bind retained REA/LLVM observations to their exact private input bytes."""
    root = results / 'video-peer-server-static-20261018'
    slice_ = load(root / 'slice-metadata.json')
    require(sha(slice_['source_path']) == slice_['source_SHA256']
            and sha(slice_['slice_path']) == slice_['slice_SHA256']
            and slice_['UUID'] == '1cfa17825c4533bdbe30d374732a91c5'
            and not slice_['vendor_code_executed'] and not slice_['system_modified'], 'private analysis slice identity')
    summary = load(root / 'static-summary.json')
    evidence = load(root / 'REA-evidence.private.json')
    matches = [r for r in evidence['records'] if r['evidence_id'] == summary['evidence_id']]
    require(len(matches) == 1, 'retained REA evidence')
    record = matches[0]
    entry = record['normalized_result']
    require(record['subject']['digest']['sha256'] == slice_['slice_SHA256']
            and record['provider']['id'] == 'ghidra' and record['provider']['version'] == '12.1.4'
            and entry['procedure']['address'] == '0x100000578'
            and entry['procedure']['body']['total_bytes'] == 16
            and any(c['name'] == '_xpc_main' for c in entry['callees'])
            and any(r['value'] == '_VTRemoteDecodeServer_XPCServiceConnectionHandler' for r in entry['referenced_names']), 'static service entry relation')
    require('_VTRemoteDecodeServer_XPCServiceConnectionHandler' in (root / 'imports.private.txt').read_text()
            and '_xpc_main' in (root / 'imports.private.txt').read_text(), 'independent import inventory')
    regions, metadata, parts = [], [], {}
    for name, offset, length in [('handler', 4268444, 101), ('callback', 4268545, 14),
                                 ('dispatch', 4268559, 140), ('messages', 4269743, 6156)]:
        folder = results / ('video-peer-server-' + name + '-20261018')
        if name == 'handler':
            cap = load(folder / 'capture.json')
            require(not cap['vendor_program_executed'] and not cap['system_modified'], 'named inspector scope')
            for source, digest in cap['source_hashes'].items():
                require(sha(folder / source) == digest, 'named inspector source')
            folder = folder / 'function-00'
            require(sha(folder / 'metadata.json') == cap['records'][0]['metadata_SHA256'], 'named metadata receipt')
            for part in cap['cache_parts_read']:
                parts[part['path']] = part['SHA256']
        m = load(folder / 'metadata.json')
        r = m['region']
        require(m['image']['UUID'] == 'e7231bea63883d0a95c0a93ce970b96b'
                and r['start_VM'] - m['image_base_VM'] == offset and r['bytes'] == length
                and sha(folder / 'function-region.private.bin') == r['SHA256']
                and r['boundary_source'] == 'LC_FUNCTION_STARTS', 'bounded static function bytes')
        metadata.append(m)
        if name != 'handler':
            require(sha(folder / 'inspector.py') == m['inspector_source_SHA256']
                    and not m['native_program_executed'] and m['region_captured_privately'], 'static inspector scope')
            analyzed = results / ('video-peer-server-' + name + '-analysis-20261018')
            a = load(analyzed / 'analysis.json')
            require(a['status'] == 'STATIC_ONLY' and not a['runtime_branch_proved']
                    and not a['vendor_program_executed'] and not a['system_modified'], 'static analysis scope')
            for source, digest in a['source_hashes'].items():
                require(sha(analyzed / source) == digest, 'static analyzer source')
            item = a['records'][0]
            require(item['metadata_SHA256'] == sha(folder / 'metadata.json')
                    and item['region_SHA256'] == r['SHA256']
                    and sha(analyzed / 'region-00/analysis.private.o') == item['container_SHA256']
                    and sha(analyzed / 'region-00/disassembly.private.txt') == item['disassembly_SHA256'], 'analysis artifact identity')
            if name == 'callback':
                require(any(j['target_image_offset'] == 4268559 for j in item['direct_jumps']), 'callback tail target')
            if name == 'dispatch':
                require(any(j['target_image_offset'] == 4269743 for j in item['direct_jumps']), 'message dispatch target')
            if name == 'messages':
                require(any(c['site_image_offset'] == 4272141 and c['target_image_offset'] == 6288668
                            for c in item['calls']), 'shared selector static call')
                text = (analyzed / 'region-00/disassembly.private.txt').read_text()
                require('cmpl\t$0x53747274, %eax' in text and 'je\t0x7ff815d98f80' in text
                        and 'testl\t%eax, %eax' in text and 'jne\t0x7ff815d99ceb' in text
                        and '7ff815d99ceb:  \tmovl\t%eax, %r13d' in text
                        and 'movslq\t%r13d, %r14' in text, 'bounded Strt/error dataflow evidence')
        regions.append({'role': name, 'image_offset': offset, 'bytes': length, 'SHA256': r['SHA256']})
    handler = results / 'video-peer-server-handler-20261018/function-00/function-region.private.bin'
    code = handler.read_bytes()
    require(code[45:48] == b'\x48\x8d\x05' and int.from_bytes(code[48:52], 'little', signed=True) + 52 == 101,
            'handler block pointer targets adjacent callback')
    for m in metadata[1:]:
        for part in m['cache_parts_read']:
            require(part['path'] not in parts or parts[part['path']] == part['SHA256'], 'cache identity drift')
            parts[part['path']] = part['SHA256']
    old = results / 'video-codec-shared-selector-20261016'
    original = load(old / 'metadata.json')
    require(original['region']['target_image_offset'] == 6288668
            and original['region']['SHA256'] == sha(old / 'function-region.private.bin')
            == '6b98a81482d8cce93ec6e651d4828edf574af91e6468b8436c484952da35d5ee', 'known shared selector identity')
    for part in original['cache_parts_read']:
        require(part['path'] not in parts or parts[part['path']] == part['SHA256'], 'selector cache drift')
        parts[part['path']] = part['SHA256']
    for path, digest in parts.items():
        require(sha(path) == digest, 'installed cache changed')
    return {'REA_evidence_id': summary['evidence_id'], 'REA_provider': record['provider'],
        'REA_bundle_SHA256': sha(root / 'REA-evidence.private.json'), 'entry_address': '0x100000578',
        'entry_bytes': 16, 'service_slice_SHA256': slice_['slice_SHA256'], 'regions': regions,
        'Strt_opcode': 1400140404, 'Strt_static_selector_call_offset': 4272141,
        'selector_target_offset': 6288668, 'runtime_server_branch_proved': False,
        'native_private_callback_ABI_and_initialization_fully_qualified': False,
        'vendor_code_invoked_by_analysis': False, 'source_or_cache_modified': False}


def audit(lab):
    lab = lab.resolve()
    results = lab / 'results'
    progress = results / 'video-peer-progress-20261018'
    build = results / 'video-peer-build-20261018'
    data = load(build / 'inputs.json')
    require(data['routing_schema'] == 3, 'observer source version')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            require(sha(build / folder / name) == digest, 'frozen build input: ' + name)
    require(len(load(build / 'commands.json')) == 6 and all(c['exit_code'] == 0
            for c in load(build / 'commands.json')), 'build completion')
    require(sha(build / 'libVideoRouting.dylib') == data['routing_library_SHA256'], 'observer library')
    for key in ('new_object_SHA256',):
        for name, digest in data[key].items():
            require(sha(build / name) == digest, 'object identity')
    for codec, digest in data['executable_variants_SHA256'].items():
        require(sha(build / ('application-' + codec)) == digest, 'executable variant')
    base = Path(data['dependency_build'])
    require(sha(base / 'inputs.json') == data['dependency_inputs_SHA256'], 'qualified dependency inputs')
    verify_base(base)
    require(data['qualified_host_source_unchanged'] and not data['qualified_host_object_reused']
            and data['catalog_and_decoder_objects_reused'] and sha(base / 'video_registry_client.mm')
            == sha(build / 'video_registry_client.mm') == data['qualified_host_source_SHA256'], 'source/object distinction')
    profile = load(build / 'assets/routing-profile.json')
    modules = {m['install_name']: m for m in profile['modules']}
    image = load(progress / 'service-image-metadata.json')
    require(sha(image['path']) == image['SHA256']
            == 'a2b9bc6cf92cb58e06506d338c7363cde19303aee9b878730e20b73a69b4efbb', 'installed service binary')
    require({'UUID': '1cfa17825c4533bdbe30d374732a91c5', 'architecture': 'x86_64'} in image['slices'], 'native service slice')
    plan = load(progress / 'case-plan.json')
    cases = [('H264', 'inspect', 'native', 'observe', 'video-peer-inspect-20261018'),
             ('H264', 'cpu', 'native', 'observe', 'video-peer-H264-cpu-20261018'),
             ('H264', 'hardware', 'present-key', 'observe', 'video-peer-H264-present-first-20261018')]
    cases += [tuple(row) for row in plan['cases']]
    require(len(cases) == 13 and len({c[-1] for c in cases}) == 13, 'planned cohort set')
    manifests, rows, crossover, peer_rows = [], [], [], []
    counts = Counter()
    private = {}
    for codec, mode, choice, peer_mode, name in cases:
        root = results / name
        run = terminal(root, lab, build)
        require(sha(root / 'runner.py') == sha(build / 'builder.py'), 'runner identity')
        for key, value in data.items():
            if key != 'assets_SHA256':
                require(run[key] == value, 'frozen run/build field: ' + key)
        require(run['selected_codec'] == codec and run['override_mode'] == choice and run['peer_mode'] == peer_mode
                and run['routing_mode'] == 'observe' and run['executable_SHA256']
                == data['executable_variants_SHA256'][codec], 'explicit run selection')
        require(set(run['assets_SHA256']) == set(data['assets_SHA256']), 'run asset set')
        for key, value in data['assets_SHA256'].items():
            if key not in ('dependency-choice.json', 'peer-choice.json'):
                require(run['assets_SHA256'][key] == value, 'invariant asset')
        require(load(root / 'assets/dependency-choice.json') == {'mode': choice}
                and load(root / 'assets/peer-choice.json') == {'mode': peer_mode}, 'choice asset')
        manifest = load(root / 'execution/manifest.json')
        require(manifest['arguments'] == [str(root / 'assets'), str(root / 'outputs'), mode], 'actual native arguments')
        manifests.append(manifest)
        d, route = load(root / 'results.json'), load(root / 'routing.json')
        require(route == load(root / 'outputs/routing.json') and route['schema'] == 3
                and route['status'] == 'COMPLETE' and route['recorders_drained']
                and route['disabled_before_snapshot'] and not route['dropped'], 'complete observer')
        require(route['peer_capture_enabled'] == (peer_mode == 'observe')
                and route['synthetic_controls_valid'] and route['synthetic_ABI_calls'] == 96
                and route['peer_control_cases'] == 20 and route['scalar_summary_controls_calls'] == 14
                and route['errno_preserved_around_interposed_calls'], 'observer controls')
        require(len(route['controls']) == 32 and all(c['trial'] == i and c['correct'] and c['callbacks'] == 1
                and c['errno_preserved'] and c['input_errno'] == 100+i and c['output_errno'] == 200+i
                for i, c in enumerate(route['controls'])), 'errno/argument/return/block forwarding')
        require(len(route['peer_controls']) == 20 and all(c['correct'] for c in route['peer_controls'])
                and [c['accepted'] for c in route['peer_controls'][:19]] == [True] + [False]*18
                and route['peer_controls'][-1]['kind'] == 'public_own_process_metadata'
                and not route['peer_controls'][-1]['remote_process_queried'], 'peer predicate/self controls')
        require(len(route['scalar_summary_controls']) == 14
                and all(c['correct'] for c in route['scalar_summary_controls']), 'summary controls')
        for key in ('synthetic_native_IPC_calls', 'system_modified', 'arguments_or_return_values_modified',
                    'async_handler_replaced', 'observer_generated_native_messages', 'message_binary_or_string_values_copied',
                    'other_process_injected', 'remote_memory_read', 'PID_reuse_fully_excluded'):
            require(not route[key], 'observer scope: ' + key)
        counts.update(mock_ABI_and_errno_calls=96, summary_controls=14, peer_controls=20)
        events = route['events']
        require(route['calls'] == len(events) and [e['ordinal'] for e in events] == list(range(len(events))), 'event ordering')
        mocks = [e for e in events if e['synthetic_control']]
        require(len(mocks) == 96 and all('peer_metadata' not in e for e in mocks), 'mock separation')
        for trial in range(32):
            create, sync, async_ = mocks[trial*3:trial*3+3]
            require([e['API'] for e in (create, sync, async_)] == ['create_mach_service', 'send_with_reply_sync', 'send_with_reply']
                    and create['flags'] == 2**63 + trial*0x100000001 and create['result_present']
                    and sync['result_present'] and not async_['result_present']
                    and scalar(sync['message'], 'opcode') == scalar(async_['message'], 'opcode') == trial
                    and scalar(sync['reply'], 'status') == -100-trial, 'mock event evidence')
        native = [e for e in events if not e['synthetic_control']]
        for event in native:
            require(not event['truncated'], 'truncated event')
            expected = modules.get(event['caller']['install_name'])
            require(expected and all(event['caller'][k] == expected[k] for k in ('UUID', 'current_version')), 'caller identity')
            dictionary_summary(event['message'])
            dictionary_summary(event['reply'])
        counts['native_XPC_records'] += len(native)
        decoder = [e for e in native if e['service'] == SERVICE]
        selected = [e for e in decoder if e['caller']['caller_offset'] in (6326974, 6327491)]
        reached = mode == 'cpu' or choice == 'present-key'
        require(bool(decoder) == reached and len(selected) == (2 if reached else 0), 'route distinction')
        if reached:
            require([scalar(e['message'], 'OpCode') for e in selected] == [1969382770, 1400140404]
                    and [scalar(e['reply'], 'Status') for e in selected] == [0, 0 if mode == 'cpu' else -12906], 'actual service statuses')
        peers = [e for e in events if 'peer_metadata' in e]
        require(len(peers) == (2 if reached and peer_mode == 'observe' else 0), 'metadata observation boundary')
        for event in peers:
            require(event in selected and event['API'] == 'send_with_reply_sync', 'peer metadata on unrelated event')
            md = event['peer_metadata']
            require(md['consistent'] and md['PID_before'] == md['PID_after'] > 0
                    and md['first_info_bytes'] == md['second_info_bytes'] == 136
                    and md['first_birth_seconds'] == md['second_birth_seconds'] > 0
                    and md['first_birth_microseconds'] == md['second_birth_microseconds']
                    and 0 <= md['first_birth_microseconds'] < 1000000
                    and md['first_birth_seconds']*1000000 + md['first_birth_microseconds'] <= md['receipt_wall_microseconds']
                    and md['path'] == image['path'] and md['path_bytes'] == len(md['path'].encode())
                    and not md['first_errno'] and not md['second_errno'] and not md['path_errno'], 'peer raw PID/birth/path consistency')
            for key in ('authenticated_peer_identity_proved', 'PID_reuse_fully_excluded', 'remote_memory_read', 'remote_process_modified'):
                require(not md[key], 'peer scope: ' + key)
            peer_rows.append(md)
        if peers:
            require(peers[0]['peer_metadata']['PID_before'] == peers[1]['peer_metadata']['PID_before']
                    and peers[0]['peer_metadata']['first_birth_seconds'] == peers[1]['peer_metadata']['first_birth_seconds']
                    and peers[0]['peer_metadata']['first_birth_microseconds'] == peers[1]['peer_metadata']['first_birth_microseconds'], 'peer changed between two observed exchanges')
        counts['peer_metadata_records'] += len(peers)
        row = {'case': name, 'codec': codec, 'mode': mode, 'choice': choice, 'peer_mode': peer_mode,
            'peer_records': len(peers), 'result_SHA256': sha(root / 'results.json'), 'routing_SHA256': sha(root / 'routing.json'),
            'inputs_SHA256': sha(root / 'inputs.json')}
        rows.append(row)
        private[name] = {'manifest': manifest, 'peers': peers}
        if mode == 'inspect':
            require(not native and not d['public_decode'], 'inspect executed decode')
            continue
        require(not any(d[k] for k in ('direct_unknown_private_call', 'system_modified', 'performance_benchmark', 'hardware_video_execution_proved')), 'codec scope')
        dep, meta = load(root / 'dependency.json'), load(root / 'metadata.json')
        require(dep == load(root / 'outputs/dependency.json') and meta == load(root / 'outputs/metadata.json')
                and dep['status'] == meta['status'] == 'COMPLETE' and dep['recorders_drained'] and meta['recorders_drained']
                and not dep['dropped'] and not meta['dropped'] and not dep['pending'] and not meta['pending']
                and dep['hardware_requirement_preserved'] and dep['public_query_controls_valid']
                and dep['profile']['scope_contract_valid'] and not dep['return_ownership_modified'], 'dependency/metadata completeness')
        require(dep['substitutions'] == int(choice == 'present-key'), 'local substitution count')
        real = [e for e in dep['events'] if not e['synthetic_control']]
        require(len(real) == (2 if codec == 'H264' and mode == 'hardware' else 0)
                and all(e['registry_ID'] == 4294968458 and not e['original_result_present']
                    and e['return_value_changed'] == (choice == 'present-key' and e['key'] == 'IOGVACodec') for e in real), 'actual GPU property queries')
        counts.update(real_GPU_queries=len(real), public_query_controls=2, dependency_scope_cases=10)
        trace = d['trace']
        require(trace['recorders_drained'] and not trace['pending'] and not trace['dropped']
                and not trace['original_instructions_modified'] and not trace['arguments_modified'], 'entry observer')
        pairs = correlate(trace, meta)
        require(len(pairs)+1 == meta['calls'] == len(meta['events']), 'metadata association completeness')
        counts['CF_metadata_associations'] += len(pairs)
        decoded = d['public_decode']
        require(decoded['fixture_samples'] == 6 and decoded['format_create_status'] == 0, 'fixture format')
        if mode == 'cpu':
            require(dep['original_specification'] == dep['forwarded_specification'] == {'EnableHardwareAcceleratedVideoDecoder': False}
                    and decoded['decode']['create_status'] == 0 and decoded['output_frames'] == 6
                    and decoded['different_bytes'] == decoded['missing_CPU_references'] == 0
                    and decoded['decode']['decode_status'] == [0]*6
                    and decoded['decode']['finish_status'] == decoded['decode']['wait_status'] == 0, 'software decode')
            for i, file in enumerate(decoded['frame_files']):
                require(file == 'vt-frame-%03d.nv12' % i, 'frame path')
                actual = (root / 'outputs' / file).read_bytes()
                reference = (root / 'assets/fixtures' / codec / ('cpu-frame-%03d.nv12' % i)).read_bytes()
                require(len(actual) == 115200 and actual == reference, 'independent pixel oracle')
                counts.update(CPU_images=1, CPU_bytes=len(actual))
        else:
            require(dep['original_specification'] == {'RequireHardwareAcceleratedVideoDecoder': True}
                    and dep['forwarded_specification'] == {'RequireHardwareAcceleratedVideoDecoder': True, 'EnableHardwareAcceleratedVideoDecoder': True}
                    and decoded['decode']['create_status'] == dep['create_status'] == -12906
                    and decoded['output_frames'] == 0 and not decoded['frame_files']
                    and not list((root / 'outputs').glob('vt-frame-*.nv12')), 'retained strict hardware failure')
            errors = [e for e in trace['events'] if e['index'] == 0]
            require([e['caller_offset'] for e in errors] == ([6290187, 20163] if choice == 'present-key' else [20163])
                    and all(e['raw_integer_arguments'][2] & 0xffffffff == (-12906 & 0xffffffff) for e in errors), 'native error sites')
            counts['hardware_failures'] += 1
        row.update(create_status=decoded['decode']['create_status'], frames=decoded['output_frames'])
        if name.startswith('video-peer-crossover-'):
            crossover.append({'case': name, 'peer_mode': peer_mode, 'peer_records': len(peers), 'create_status': -12906,
                'raw_executable_SHA256': run['executable_SHA256'], 'signed_executable_SHA256': manifest['signed_binary_sha256'],
                'assets_SHA256': run['assets_SHA256']})
    require(len(crossover) == 6 and all(len({r[k] for r in crossover}) == 1 for k in
            ('raw_executable_SHA256', 'signed_executable_SHA256')), 'same crossover executable')
    invariant = {k: v for k, v in crossover[0]['assets_SHA256'].items() if k != 'peer-choice.json'}
    require(all({k: v for k, v in r['assets_SHA256'].items() if k != 'peer-choice.json'} == invariant for r in crossover), 'only peer asset differs')
    for row in crossover:
        del row['assets_SHA256']
    ordered = sorted(manifests, key=lambda m: m['started_at'])
    require([Path(m['original_executable']).parent.name for m in ordered] == [c[-1] for c in cases], 'actual planned order')
    for a, z in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(a['completed_at']) <= datetime.datetime.fromisoformat(z['started_at']), 'overlapping host cohorts')
    require(counts['CPU_images'] == 18 and counts['CPU_bytes'] == 2073600 and counts['hardware_failures'] == 9
            and counts['peer_metadata_records'] == 14 and counts['mock_ABI_and_errno_calls'] == 1248
            and counts['summary_controls'] == 182 and counts['peer_controls'] == 260, 'cohort totals')
    require(len({(r['PID_before'], r['first_birth_seconds'], r['first_birth_microseconds']) for r in peer_rows}) == 7, 'distinct observed peer births')
    logs = results / 'video-peer-server-logs-20261018-01'
    log_summaries = []
    for command in load(logs / 'commands.json'):
        name = command['case']
        peer = private[name]['peers'][0]['peer_metadata']
        manifest = private[name]['manifest']
        file = logs / (name + '.private.json')
        require(command['exit_code'] == 0 and sha(file) == command['stdout_SHA256']
                and sha(logs / (name + '.stderr')) == command['stderr_SHA256'], 'bounded log receipt')
        records = load(file)
        require(records and all(e['processID'] == peer['PID_before'] and e['processImagePath'] == image['path']
                and e['processImageUUID'].replace('-', '').lower() == '1cfa17825c4533bdbe30d374732a91c5' for e in records), 'independent log process identity')
        first = datetime.datetime.fromisoformat(manifest['started_at']) - datetime.timedelta(seconds=1)
        last = datetime.datetime.fromisoformat(manifest['completed_at']) + datetime.timedelta(seconds=1)
        require(all(first <= datetime.datetime.strptime(e['timestamp'], '%Y-%m-%d %H:%M:%S.%f%z') <= last
                    for e in records), 'log time boundary')
        clients = [int(pid) for e in records for pid in re.findall(r'videodecoder\.peer\[(\d+)\]', e.get('eventMessage', ''))]
        require(clients == [manifest['pid']], 'logged service peer does not match our client')
        log_summaries.append({'case': name, 'log_SHA256': sha(file), 'entries': len(records),
            'client_PID_correlated': True, 'image_UUID_and_path_match': True,
            'private_message_entries': sum(e.get('eventMessage') == '<private>' for e in records),
            'root_cause_proved': False})
    require(len(log_summaries) == 2, 'software/hardware log controls')
    patch = lab.parent / 'patches/video-routing-v2-to-v3.patch'
    old = results / 'video-routing-build-20261018-02'
    expected_patch = ''
    for source, name in [('video_routing.mm', 'video_routing.mm'), ('native_video_routing.py', 'builder.py')]:
        expected_patch += ''.join(difflib.unified_diff((old / name).read_text().splitlines(True),
            (build / name).read_text().splitlines(True), fromfile='a/bridge/tools/' + source, tofile='b/bridge/tools/' + source))
    require(patch.read_text() == expected_patch, 'source reconstruction patch')
    receipt = load(progress / 'source-reconstruction.json')
    require(receipt['status'] == 'PASS' and receipt['patch_SHA256'] == sha(patch) and receipt['verify_base_function_unchanged'], 'source reconstruction receipt')
    for source, name in [('video_routing.mm', 'video_routing.mm'), ('native_video_routing.py', 'builder.py')]:
        require(receipt['reconstructed_v2'][source] == sha(old / name)
                == sha(progress / 'reconstructed-v2/bridge/tools' / source), 'reconstructed source bytes')
    start = load(progress / 'start.json')
    require(len(start['system_before']) == 83, 'protected system inventory')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'protected file changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256']
            and sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == start['policy_SHA256'], 'OCLP/video policy changed')
    runtime = results / 'native-allocation-runtime-build-20261016-04'
    pins = load(runtime / 'manifest.json')['source_SHA256']
    require(len(pins) == 36 and all(sha(lab / name) == digest for name, digest in pins.items()), 'common runtime sources')
    require(sha(runtime / 'libKeplerMetal.a') == start['shared_runtime_archive_SHA256']
            == '5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67', 'common runtime archive')
    static = static_entry(results)
    return {'status': 'PASS', 'auditor_SHA256': sha(__file__), 'native_host_processes_terminal': 13,
        'nonoverlapping': True, 'counts': dict(counts), 'CPU_different_bytes': 0,
        'hardware_video_execution_proved': False, 'hardware_create_status': -12906,
        'observed_peer_path': image['path'], 'observed_peer_image_UUID': '1cfa17825c4533bdbe30d374732a91c5',
        'installed_service_file_SHA256': image['SHA256'], 'distinct_consistent_peer_births': 7,
        'logs': log_summaries, 'crossover': crossover, 'source_version_patch_SHA256': sha(patch),
        'v2_source_reconstruction_verified': True, 'system_files_unchanged': 83,
        'video_policy_unchanged': True, 'OCLP_unchanged': True, 'common_runtime_sources_unchanged': 36,
        'common_runtime_archive_SHA256': start['shared_runtime_archive_SHA256'],
        'authenticated_peer_identity_proved': False, 'PID_reuse_fully_excluded': False,
        'remote_memory_read': False, 'remote_process_modified': False, 'remote_provider_inventory_complete': False,
        'service_refusal_root_cause_proved': False, 'full_objective_complete': False,
        'performance_benchmark': 'NOT RUN', 'system_deployment': 'NOT RUN', 'new_M1_execution': False,
        'Qwen_job_ids': [], 'static_entry': static, 'processes': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Audit destination exists')
    report = audit(args.lab_root)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('status', 'native_host_processes_terminal', 'counts',
        'distinct_consistent_peer_births', 'hardware_video_execution_proved')}))


if __name__ == '__main__':
    main()
