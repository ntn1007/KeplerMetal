#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-audit recorded legacy AppleGVA input observations, without execution."""
import argparse
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path

BUILD = 'video-provider-fields-build-20261027-01'
BUILD_HASH = '53b898e441ba93d489842b3c8d862cfd8b3a2b04704432dfa85e10f6a5cc93f5'
REA_HASH = '62b0b5c4d5f3d455e59ed1dd6ed392d710c29c898c1e476cf1b67a43c87f9027'
OBSERVER_HASH = 'f5a02c68c5a318dbdd062b59c84fdbb3df0e7bef4c758523a0def2fc40a59e60'
CASES = [
 ('video-provider-fields-enabled-20261027-01', 'hardware', 'enabled', 'e76e30439535b99a65cd24d28825cf3b62683b1c2b4d2ef5cc02439554ac45a3', '7f12a062de45cfcc71fef295d5c0177770c640a16947a1657cef64cc4b1b2bfb'),
 ('video-provider-fields-enabled-02-20261027-01', 'hardware', 'enabled', 'e76e30439535b99a65cd24d28825cf3b62683b1c2b4d2ef5cc02439554ac45a3', '7f12a062de45cfcc71fef295d5c0177770c640a16947a1657cef64cc4b1b2bfb'),
 ('video-provider-fields-wrong-name-20261027-01', 'hardware', 'wrong-name', 'fb76ffc6aa58d19c51cc0ee339c283c94cf1b5ddbf2d8b1a1a4b9ab03c63cb26', '97f1af643303a05341f28a4ba7432ac044a4b9f72c58ac0321588328e5709126'),
 ('video-provider-fields-cpu-20261027-01', 'cpu', 'passive', '7b871fb9f943346a20770ad357b34fbbeb0c9fd6b2e1a8db4a718e405422313f', 'bf334104114089ac705e5dd9466c6ebbb67aedc16e8481b20ec9382daab80e4a'),
]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_capture(gate, route):
    require(gate['status'] == 'COMPLETE' and gate['calibration_pass'] and gate['drained'] and not gate['dropped'], 'gate incomplete')
    require(not gate['sierra_loaded'] and not gate['sierra_export_called'] and gate['gate_return'] == 14, 'unexpected provider use')
    obs = gate['argument_observation']
    if route == 'enabled':
        require(gate['gate_calls'] == 1 and obs['ready'] and obs['caller_offset'] == 0x24d16, 'call site')
        for name in ('caller_pinned', 'caller_path_matches', 'caller_UUID_matches', 'config_header_20_read',
                     'display_array_region_readable', 'selected_index_in_mask', 'selected_index_in_range',
                     'selected_display_value_nonzero', 'region_is_not_allocation_size_proof'):
            require(obs[name] is True, 'observation: ' + name)
        require((obs['config_first_word'], obs['display_mask'], obs['display_array_required_count']) == (0, 15, 4), 'header differs')
        events = [e for e in gate['events'] if e['name'] == 'AVD_CreateAVDAccelerator']
        require(len(events) == 1 and events[0]['found'] and events[0]['identity_pin'] and events[0]['result_replaced'], 'lookup differs')
    else:
        require(gate['gate_calls'] == 0 and not obs['ready'], 'negative route reached gate')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    require(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    r = a.lab.resolve() / 'results'
    build = r / BUILD
    require(sha(build/'inputs.json') == BUILD_HASH, 'build manifest changed')
    b = read(build/'inputs.json')
    for name, expected in b['frozen'].items():
        require(sha(build/name) == expected, 'frozen build: ' + name)
    require(sha(build/'src/video_provider_fields_observer.mm') == OBSERVER_HASH, 'observer source changed')
    source = (build/'src/video_provider_fields_observer.mm').read_text()
    for token in ('mach_vm_read_overwrite', 'capture.callerOffset==0x24d16', 'capture.count++',
                  'capture.selectedNonzero=value!=0', 'return 14;', '@"sierra_export_called":@NO'):
        require(token in source, 'observer source invariant')
    rea = r/'video-legacy-contract-progress-20261018/REA-provider-node.private.json'
    require(sha(rea) == REA_HASH, 'legacy evidence changed')
    records = {e['evidence_id']: e for e in read(rea)['records']}
    enum = records['ev_b8d0e019961dce4a92baaefb08770f71b7830c7d8c55e4f09d0732aae0c4bdf4']
    factory = records['ev_1c3931444c6da1b092d4267c7a1d137c9039710fdac35812b98217fae6219320']
    for evidence in (enum, factory):
        require(evidence['subject']['digest']['sha256'] == '54dc80c41bab45492d1eb601fb1d242b513107645d068bf24edee155b965681f', 'GVA evidence identity')
    for token in ('piVar12 = &DAT_000f5038 + uVar21;', '_CGSAcceleratorForDisplayAlias', 'piVar12,&local_508'):
        require(token in enum['normalized_result']['pseudocode'], 'enumeration evidence')
    for token in ('local_1b8 = &DAT_000f5038;', 'local_1b0 = *(uint *)(lVar2 + 0x428);', '(&local_48,local_1c0,local_170)'):
        require(token in factory['normalized_result']['pseudocode'], 'factory evidence')
    rows = []
    intervals = []
    pids = set()
    for name, mode, route, input_hash, gate_hash in CASES:
        d = r/name
        require(sha(d/'inputs.json') == input_hash and sha(d/'provider-gate.json') == gate_hash, 'case identity')
        inp = read(d/'inputs.json')
        require(inp['build_manifest_SHA256'] == BUILD_HASH and inp['mode'] == mode and inp['route'] == route, 'case route')
        for asset, expected in inp['assets_SHA256'].items():
            require(sha(d/'assets'/asset) == expected, 'case asset: ' + asset)
        man = read(d/'execution/manifest.json')
        lease = man['GPU_reservation']
        require(man['exit_code'] == 0 and not man['SIGKILL_requested'] and not man['authoritative_ps_status'] and lease['state'] == 'terminal' and lease['child_PID'] == man['pid'] and lease['exit_code'] == 0 and not lease['known_signed_processes_live'], 'nonterminal process')
        require(man['pid'] not in pids, 'reused pid')
        pids.add(man['pid'])
        intervals.append((datetime.fromisoformat(man['started_at']), datetime.fromisoformat(man['completed_at'])))
        require(sha(d/'application') == man['original_binary_sha256'] == b['frozen']['application'] and sha(d/'execution/application') == man['signed_binary_sha256'] == lease['signed_binary_sha256'], 'application mismatch')
        subprocess.run(['codesign', '--verify', '--strict', str(d/'execution/application')], capture_output=True, check=True)
        gate = read(d/'provider-gate.json')
        require(gate == read(d/'outputs/provider-gate.json'), 'gate output mismatch')
        check_capture(gate, route)
        result = read(d/'result.json')
        require(result == read(d/'execution/execution.stdout'), 'stdout mismatch')
        result = result['public_decode']
        if mode == 'hardware':
            require(result['decode']['specification']['RequireHardwareAcceleratedVideoDecoder'] is True and result['decode']['create_status'] == -12913 and result['output_frames'] == 0, 'hardware result')
        else:
            require(result['decode']['create_status'] == 0 and result['output_frames'] == 6 and result['different_bytes'] == 0, 'CPU result')
            for i in range(6):
                frame = (d/'outputs'/f'vt-frame-{i:03d}.nv12').read_bytes()
                ref = (d/'assets/fixtures/H264'/f'cpu-frame-{i:03d}.nv12').read_bytes()
                require(frame == ref and len(frame) == 460800, 'CPU image differs')
        rows.append({'mode': mode, 'route': route, 'gate_calls': gate['gate_calls'], 'gate_sha256': gate_hash})
    intervals.sort()
    require(all(a <= b for a, b in intervals) and all(x[1] <= y[0] for x, y in zip(intervals, intervals[1:])), 'process overlap')
    out = {'status': 'PASS', 'prior_runs_reaudited': 4, 'nonoverlapping_terminal_processes': 4,
           'observed_calls': 2, 'index': 0, 'mask': 15, 'required_vector_words': 4,
           'selected_entry_nonzero': True, 'complete_vector_read': False,
           'software_images': 6, 'software_cpu_reference_bytes': 2764800,
           'hardware_required_failures': 3, 'hardware_images': 0,
           'sierra_provider_loaded_by_gate': False, 'historical_GVA_was_explicitly_selected': True,
           'scope': 'Archived process-local legacy path and private-API replacement; no new runtime execution or actual provider integration.',
           'cases': rows, 'build_inputs_SHA256': BUILD_HASH, 'observer_source_SHA256': OBSERVER_HASH, 'REA_bundle_SHA256': REA_HASH}
    with a.out.open('x') as f:
        json.dump(out, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(out, sort_keys=True))


if __name__ == '__main__':
    main()
