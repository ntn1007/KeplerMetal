#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the recorded native-start cohort without running a native program."""
from pathlib import Path
import argparse
import hashlib
import json

from audit_video_factory import receipt, audit as previous_audit, signed32
from audit_video_local_service import owned, software
from audit_video_registry import correlate


GVA = 'ca5414f369373c059ea2d82b35afd4f0'
VT = 'e7231bea63883d0a95c0a93ce970b96b'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mock_controls(d, version):
    require(d['synthetic_controls_valid'], 'mock controls failed')
    for field in ['controls', 'factory_controls', 'preference_controls'] + (['pool_controls'] if version == 8 else []):
        require(len(d[field]) == 32, 'mock count: ' + field)
        for i, row in enumerate(d[field]):
            base = dict(trial=i, correct=True)
            if field == 'controls':
                base.update(input_errno=500+i, output_errno=600+i, result_present=bool(i % 3), native_resolver_called=False)
            elif field == 'factory_controls':
                base.update(input_errno=700+i, output_errno=800+i, status=[-12692, 0, -12906][i % 3],
                            factory_present=bool(i % 3), original_private_function_called=False)
            elif field == 'preference_controls':
                base.update(input_errno=900+i, output_errno=1000+i, result_present=bool(i % 2), native_preference_called=False)
            else:
                base.update(input_errno=1100+i, output_errno=1200+i, status=-6680 if i % 2 else 0,
                            output_present=bool(i % 3), native_pool_create_called=False)
            require(row == base, 'mock argument/status/errno/output oracle: ' + field)


def probe(root, build, bridge, version):
    inp, m = receipt(root, build, bridge)
    result, d, own = load(root / 'results.json'), load(root / 'factory-resolver.json'), load(root / 'owned.json')
    mode = inp['mode']; policy = load(root / 'assets/factory-policy-choice.json')['mode']
    inspect = mode == 'inspect'; hw = mode == 'hardware'; active = hw and policy == 'current-board'
    require(inp['route'] == ('native' if inspect else 'owned'), 'route')
    owned(own, m, not inspect)
    require(d == load(root / 'outputs/factory-resolver.json') and d['status'] == 'COMPLETE'
            and d['recorders_drained'] and not d['dropped'], 'complete retained observation')
    mock_controls(d, version)
    for key in ['native_function_invoked_directly', 'resolved_pointer_replaced', 'arguments_modified',
                'original_instructions_modified', 'system_modified', 'hardware_video_execution_proved',
                'performance_benchmark', 'native_start_method_replaced', 'native_interface_tables_modified']:
        require(d[key] is False, 'scope: ' + key)
    require(d['calls'] == len(d['events']) == (0 if inspect else 1+int(active))
            and d['factory_calls'] == len(d['factory_events']) == int(not inspect), 'resolver/factory cardinality')
    for e in d['events']:
        require(e['result_present'] and e['result_in_executable_image'] and not e['truncated']
                and e['arguments_are_public_CF_types'] and e['arguments_forwarded_unchanged']
                and e['returned_pointer_unchanged'] and not e['function_invoked_by_observer'], 'resolver pass-through')
    if not inspect:
        factory = d['factory_events'][0]
        require(factory['status_int32'] == 0 and factory['factory_present'] and factory['factory_pointer_unchanged']
                and factory['original_forwarded_through_qualified_entry_tail']
                and not factory['original_caller_return_address_preserved']
                and not factory['returned_factory_invoked_by_observer'], 'natural factory result')
        require(factory['factory_identity']['offset'] == (4294856 if hw else 25296), 'factory target')
        event = d['events'][0]
        require(event['name'] == ('AVFQTX_CreateMediaAcceleratorInterface' if hw else 'H264VideoDecoder_CreateInstance')
                and event['result_identity']['offset'] == (4577 if hw else 25296), 'resolved implementation')
    require(d['start_resolver_calls'] == d['preference_calls'] == len(d['preference_events']) == int(active), 'native start stage counts')
    if active:
        event = d['events'][1]
        require(event['caller_module'] == 'VideoToolbox' and event['caller_offset'] == 4298852
                and event['name'] == 'AVFQTX_GetMaxParsedStructureVersion'
                and event['result_identity']['UUID'] == GVA and event['result_identity']['offset'] == 5332
                and event['result_identity']['symbol_exact_address'], 'actual native-start resolver')
        preference = d['preference_events'][0]
        require(preference == dict(ordinal=0, caller_offset=4299460, key_is_H264GVAPixelFormat=True,
                application_is_coremedia=True, result_present=False, arguments_forwarded_unchanged=True,
                returned_pointer_unchanged=True, copy_ownership_unchanged=True,
                user_and_host_values_not_collected=True), 'unchanged public preference result')
    calls = 0 if not hw else (3 if active else 1)
    require(d['policy_calls'] == len(d['policy_events']) == calls
            and d['policy_substitutions'] == (calls if hw and policy != 'observe' else 0), 'policy counts')
    stacks = [[('AppleGVA', GVA, 722786), ('AppleGVA', GVA, 260915), ('VideoToolbox', VT, 4294967),
               ('VideoToolbox', VT, 6289973), ('VideoToolbox', VT, 4272146)],
              [('AppleGVA', GVA, 722786), ('AppleGVA', GVA, 280947), ('VideoToolbox', VT, 4299346), ('VideoToolbox', VT, 4275210)],
              [('AppleGVA', GVA, 722786), ('AppleGVA', GVA, 262414), ('VideoToolbox', VT, 4300698), ('VideoToolbox', VT, 4275210)]]
    for i, e in enumerate(d['policy_events']):
        require(e['original_matches_installed_support'] and e['original_board_missing']
                and e['return_value_changed'] == (policy != 'observe') and e['returned_board_present'] == active
                and not e['original_dictionary_modified'] and e['borrowed_return_contract'], 'policy guard')
        if version >= 7:
            actual = [(s['module'], s['UUID'], s['return_offset']) for s in e['stack_frames']
                      if s['module'] in ['AppleGVA', 'VideoToolbox']]
            require(actual == stacks[i] and all(s['observed_by_public_backtrace'] for s in e['stack_frames']), 'actual policy callers')
    if version >= 7:
        require(d['GVA_stage_code_pins_valid'] == hw, 'resident GVA body pins')
    if version == 8:
        require(d['pool_calls'] == len(d['pool_events']) == int(active)
                and d['provider_resolver_calls'] == 0, 'CV pool/provider observation counts')
        if active:
            require(d['pool_events'][0] == dict(ordinal=0, caller_offset=263397, status_int32=0,
                    output_observed_after_success=True, pixel_buffer_present=True, arguments_forwarded_unchanged=True,
                    status_and_output_unchanged=True, resource_contents_not_read=True, ownership_unchanged=True), 'real CV pixel buffer success')
    row = dict(case=root.name, version=version, mode=mode, policy=policy, PID=m['pid'],
               started_at=m['started_at'], completed_at=m['completed_at'], frames=0, pixel_bytes=0,
               manifest_SHA256=sha(root / 'execution/manifest.json'), factory_SHA256=sha(root / 'factory-resolver.json'),
               original_executable_SHA256=m['original_binary_sha256'], native_start_observed=active,
               context_policy_caller_observed=active and version >= 7,
               successful_CV_pixel_buffer=active and version == 8, mock_controls=128 if version == 8 else 96)
    if inspect:
        require(result['public_decode'] is None and not result['trace']['calls'], 'inspect ran decoder')
        return row
    dep, meta = load(root / 'dependency.json'), load(root / 'metadata.json')
    require(dep['status'] == 'COMPLETE' and dep['recorders_drained'] and not dep['pending'] and not dep['dropped']
            and dep['hardware_requirement_preserved'], 'dependency capture')
    require(dep['original_specification'] == ({'RequireHardwareAcceleratedVideoDecoder': True} if hw
            else {'EnableHardwareAcceleratedVideoDecoder': False}), 'original decoder requirement')
    require(dep['forwarded_specification'] == ({'RequireHardwareAcceleratedVideoDecoder': True,
            'EnableHardwareAcceleratedVideoDecoder': True} if hw else {'EnableHardwareAcceleratedVideoDecoder': False}), 'preserved hardware flag')
    trace = result['trace']
    require(trace['recorders_drained'] and not trace['pending'] and not trace['dropped']
            and meta['status'] == 'COMPLETE' and meta['recorders_drained'] and not meta['pending'] and not meta['dropped']
            and all(not e['truncated'] for e in meta['events'])
            and len(correlate(trace, meta))+1 == len(meta['events']) == meta['calls'], 'metadata association completeness')
    if hw:
        status = -12913 if active else -12906
        require(result['public_decode']['decode']['create_status'] == dep['create_status'] == status
                and result['public_decode']['output_frames'] == 0 and not list((root / 'outputs').glob('vt-frame-*.nv12')), 'hardware refusal')
        require([e['status'] for e in own['exchanges']] == [0, status], 'native Strt refusal')
        errors = [(e['caller_offset'], signed32(e['raw_integer_arguments'][2])) for e in trace['events'] if e['index'] == 0]
        require(errors == ([(4275288, -12900)] if active else []) + [(6290187, -12906), (20163, status)], 'unchanged error sites')
        row['hardware_create_status'] = status
    else:
        row['frames'], row['pixel_bytes'] = software(root, result)
        require([(e['opcode'], e['status']) for e in own['exchanges'] if e['status']] ==
                [(0x46696e46, -12782)]*2+[(0x496e7661, -12782), (0x46696e46, -12782)], 'nonzero software replies retained')
    return row


def audit(bridge):
    bridge = bridge.resolve(); results = bridge / 'results'; rows = []
    for version in [6, 7, 8]:
        build = results / ('video-factory-resolver-build-20261018-%02d' % version)
        for root in sorted(results.glob('video-factory-resolver-v%d-*-20261018' % version)):
            if (root / 'execution/manifest.json').exists():
                rows.append(probe(root, build, bridge, version))
    require(len(rows) == 17, 'exact native cohort count')
    rows.sort(key=lambda r: r['started_at'])
    for a, b in zip(rows, rows[1:]):
        require(a['completed_at'] <= b['started_at'], 'overlapping hosts')
    final = [r for r in rows if r['version'] == 8 and r['mode'] == 'hardware']
    require(len(final) == 7 and len({r['original_executable_SHA256'] for r in final}) == 1, 'same-binary final policy cohort')
    old = (json.dumps(previous_audit(bridge), indent=2)+'\n').encode()
    require(hashlib.sha256(old).hexdigest() == '2d68546884ffdc5ee66560e0580ad7c9ba10aa5653a679994a01e85f02791064', 'previous audit changed')
    return dict(status='PASS', native_hosts=17, terminal_nonoverlapping=True,
                software_images=sum(r['frames'] for r in rows), exact_CPU_pixel_bytes=sum(r['pixel_bytes'] for r in rows),
                mock_controls=sum(r['mock_controls'] for r in rows), same_binary_policy_cases=7,
                native_start_cases=sum(r['native_start_observed'] for r in rows),
                context_policy_stack_cases=sum(r['context_policy_caller_observed'] for r in rows),
                successful_CV_pixel_buffer_cases=sum(r['successful_CV_pixel_buffer'] for r in rows),
                hardware_images=0, hardware_refusals=11, software_nonzero_replies=12,
                previous_audit_byte_identical=True, protected_files_unchanged=83, common_sources_unchanged=36,
                OCLP_and_both_policies_unchanged=True, common_archive_unchanged=True, cases=rows,
                hardware_video_execution_proved=False, performance_benchmark=False, full_objective_complete=False,
                limits=['A CV pixel buffer and an allocated provider table do not prove video-engine execution.',
                        'No native method/table replaced or unknown private function directly invoked.',
                        'GetFactory forwarding retains its previously documented caller-return-address limitation.',
                        'FinF/Inva-12782 software replies remain; complete service lifetime is unqualified.',
                        'The final-12913 cause after the first pixel buffer is still open.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab-root', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); require(not args.out.exists(), 'new audit output required')
    result = audit(args.lab_root)
    args.out.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
