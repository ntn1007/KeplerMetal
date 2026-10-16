#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit public H264/MPEG2 policy experiments and the independent CPU fixture.

Reads named private laboratory receipts; launches no codec, GPU work or tool.
Failure to allocate hardware is retained as failure, not recast as GPU success.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json

from audit_video_images import sha, load, catalog, POLICY_SHA
from verify_native_control_reserve import terminal, require


def audit(lab):
    results = lab / 'results'
    progress = results / 'video-codec-policy-progress-20261016'
    start = load(progress / 'start.json')
    prior = results / 'video-images-progress-20261016/audit-video-images.json'
    require(sha(prior) == start['previous_audit_SHA256'], 'prior qualified audit changed')
    pinned_inspect = results / 'video-policy-inspect-20261016/results.json'
    prior_row = next(x for x in load(prior)['processes'] if x['cohort'] == 'video-policy-inspect-20261016')
    require(sha(pinned_inspect) == prior_row['result_SHA256'], 'prior resident pin evidence changed')
    expected_pins = load(pinned_inspect)['resident_code_pins']
    returned = progress / 'M1-mpeg2-return'
    source = load(progress / 'M1-output-source-hashes.json')
    for name, entry in source.items():
        path = returned / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == entry['bytes']
                and sha(path) == entry['SHA256'], 'reference transfer differs')
    transfer = load(progress / 'M1-source-transfer.json')
    require(transfer['source_SHA256'] == transfer['remote_source_SHA256']
            == sha(lab / 'tools/generate_mpeg2_reference.py'), 'reference generator source identity')
    reference = load(returned / 'manifest.json')
    require(reference['status'] == 'PASS' and reference['architecture'] == 'arm64'
            and reference['hardware_acceleration'] == 'none'
            and reference['frames'] == 6 and reference['decoded_bytes'] == 691200, 'reference scope')
    require(sha(returned / 'commands.json') == reference['commands_SHA256'], 'reference commands changed')
    commands = load(returned / 'commands.json')
    require(len(commands) == 3 and [x['label'] for x in commands] == ['encode', 'decode', 'packets'], 'CPU reference commands')
    for i, command in enumerate(commands):
        require(command['exit_code'] == 0 and not command['SIGKILL_requested']
                and not command['authoritative_ps_status'], 'CPU reference process nonterminal')
        require(sha(returned / (command['label'] + '.stdout')) == command['stdout_SHA256']
                and sha(returned / (command['label'] + '.stderr')) == command['stderr_SHA256'], 'reference log changed')
        if i < 2:
            args = command['argv']
            require(args[args.index('-hwaccel') + 1] == 'none' and 'mpeg2video' in args
                    and 'videotoolbox' not in args, 'software codec selection')
        if i:
            require(commands[i - 1]['completed_at'] <= command['started_at'], 'overlapping reference commands')
    data = (returned / 'fixture.m2v').read_bytes()
    pixels = (returned / 'decoded.nv12').read_bytes()
    require(len(data) == reference['packet_bytes'] == 11871 and len(pixels) == 691200
            and sha(returned / 'fixture.m2v') == reference['compressed_SHA256']
            and sha(returned / 'decoded.nv12') == reference['decoded_SHA256'], 'MPEG2 reference files')
    fixture = load(returned / 'fixture/fixture.json')
    packets = load(returned / 'packets.stdout')['packets']
    require(len(packets) == len(fixture['frames']) == 6, 'reference packet count')
    offset = 0
    for i, (packet, frame) in enumerate(zip(packets, fixture['frames'])):
        packet_start, count = int(packet['pos']), int(packet['size'])
        compressed = (returned / 'fixture' / frame['file']).read_bytes()
        digest = hashlib.sha256(compressed).hexdigest()
        require(packet_start == offset and compressed == data[packet_start:packet_start + count] and len(compressed) == frame['bytes']
                and 'K' in packet['flags'] and packet['data_hash'].lower() == 'sha256:' + digest
                and digest == frame['SHA256'], 'packet boundary/data mismatch')
        require((returned / 'fixture' / ('cpu-frame-%03d.nv12' % i)).read_bytes()
                == pixels[i * 115200:(i + 1) * 115200], 'reference image slice')
        offset += count
    require(offset == len(data), 'unaccounted bitstream bytes')
    for name, digest in reference['fixture_files_SHA256'].items():
        require(sha(returned / 'fixture' / name) == digest, 'reference asset changed')

    cases = []
    for mode, suffix in [('inspect', ''), ('cpu', ''), ('native', ''), ('wrong-model', ''), ('model-entry', ''), ('native', '-after')]:
        cases.append(('H264', 'video-codec-policy-build-20261016',
                      'video-codec-policy-' + mode + suffix + '-20261016', mode))
        cases.append(('MPEG2Video', 'video-codec-policy-mpeg2-build-20261016',
                      'video-codec-policy-mpeg2-' + mode + suffix + '-20261016', mode))
    for mode in ('cpu', 'native'):
        cases.append(('H264', 'video-codec-policy-h264-build-20261016-02',
                      'video-codec-policy-h264-' + mode + '-20261016-02', mode))
    counts = {c: {'CPU_processes': 0, 'CPU_frames': 0, 'CPU_reference_bytes': 0,
                  'hardware_required_failures': 0, 'hardware_frames': 0} for c in ('H264', 'MPEG2Video')}
    rows, receipts = [], []
    for codec, build, name, mode in cases:
        root = results / name
        inputs = terminal(root, lab, results / build)
        require(inputs == load(results / build / 'inputs.json'), 'frozen build input identity')
        require(sha(results / build / 'libVideoPolicyObserver.dylib') == inputs['policy_library_SHA256'], 'observer changed')
        d, m = load(root / 'results.json'), load(root / 'execution/manifest.json')
        receipts.append(m)
        require(d['codec'] == codec and d['mode'] == mode and not d['private_query_invoked_by_host']
                and not d['unknown_private_factory_or_decoder_invoked_by_host']
                and not d['hardware_video_execution_proved'] and not d['system_modified']
                and not d['performance_benchmark'], 'public codec scope')
        require(d['policy_SHA256_before'] == d['policy_SHA256_after'] == POLICY_SHA, 'system policy changed')
        trace = d['policy']
        require(trace['dropped'] == 0 and trace['configuring_thread_only'] and trace['disabled_before_snapshot']
                and not trace['system_file_modified'] and not trace['driver_instructions_modified'], 'observer scope')
        events = trace['events']
        require(d['resident_code_pins'] == expected_pins, 'resident preflight differs from qualified profile')
        if mode == 'inspect':
            require(d['public_decode'] is None and not events, 'inspect called codec')
        else:
            require(len(events) == 1 and events[0]['synthetic_calibration']
                    and not events[0]['pinned_native_callsite'] and events[0]['original_data_hash_verified']
                    and events[0]['return_data_changed'] == (mode in ('wrong-model', 'model-entry'))
                    and d['calibration_model_entry_present'] == (mode == 'model-entry'), 'calibrated observation')
            decoded = d['public_decode']
            require(decoded['format_create_status'] == 0 and decoded['fixture_samples'] == 6, 'valid format/sample count')
            if mode == 'cpu':
                require(decoded['decode']['create_status'] == 0 and decoded['output_frames'] == 6
                        and decoded['CPU_reference_bytes_compared'] == 691200
                        and decoded['different_bytes'] == decoded['missing_CPU_references'] == 0
                        and decoded['decode']['specification'] == {'EnableHardwareAcceleratedVideoDecoder': False}
                        and not decoded['decode']['callback_errors'], 'software control')
                for i, filename in enumerate(decoded['frame_files']):
                    actual = (root / 'outputs' / filename).read_bytes()
                    expected = (root / 'assets/fixture' / ('cpu-frame-%03d.nv12' % i)).read_bytes()
                    require(len(actual) == 115200 and actual == expected, 'software image bytes')
                counts[codec]['CPU_processes'] += 1
                counts[codec]['CPU_frames'] += 6
                counts[codec]['CPU_reference_bytes'] += 691200
            else:
                require(decoded['decode']['create_status'] == -12906 and decoded['output_frames'] == 0
                        and not decoded['frame_files'] and decoded['CPU_reference_bytes_compared'] == 0
                        and decoded['decode']['specification'] == {'RequireHardwareAcceleratedVideoDecoder': True}, 'retained hardware failure')
                counts[codec]['hardware_required_failures'] += 1
        images = load(root / 'images.json')
        catalog(images['before'])
        catalog(images['after'])
        rows.append({'cohort': name, 'codec': codec, 'mode': mode, 'process_terminal': True,
            'result_SHA256': sha(root / 'results.json'), 'manifest_SHA256': sha(root / 'execution/manifest.json')})
    require(counts['H264']['hardware_required_failures'] == 5
            and counts['MPEG2Video']['hardware_required_failures'] == 4, 'hardware trial count')
    receipts.sort(key=lambda x: x['started_at'])
    for before, after in zip(receipts, receipts[1:]):
        require(datetime.datetime.fromisoformat(before['completed_at']) <=
                datetime.datetime.fromisoformat(after['started_at']), 'overlapping native processes')
    require(len(start['system_before']) == 83, 'system inventory')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'system file changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256'], 'OCLP changed')
    require(sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == POLICY_SHA, 'policy changed')
    common = load(results / 'native-allocation-runtime-build-20261016-04/manifest.json')
    require(len(common['source_SHA256']) == 36, 'common runtime source inventory')
    for name, digest in common['source_SHA256'].items():
        require(sha(lab / name) == digest, 'common runtime source changed')
    selection = results / 'video-codec-selection-cache-20261016'
    capture = load(selection / 'capture.json')
    require(capture['image_UUID'] == 'e7231bea63883d0a95c0a93ce970b96b'
            and not capture['vendor_program_executed'], 'static VT identity')
    for name, digest in capture['source_hashes'].items():
        require(sha(selection / name) == digest, 'static inspector source changed')
    for row in capture['records']:
        folder = selection / row['folder']
        require(sha(folder / 'metadata.json') == row['metadata_SHA256']
                and sha(folder / 'function-region.private.bin') == row['region_SHA256'], 'public entry capture changed')
    parts = capture['cache_parts_read']
    require(len(parts) == 1 and sha(parts[0]['path']) == parts[0]['SHA256'], 'shared cache file changed')
    for name in ['video-codec-create-implementation-20261016', 'video-codec-hardware-selection-20261016']:
        folder = results / name
        meta = load(folder / 'metadata.json')
        require(meta['image']['UUID'] == capture['image_UUID']
                and sha(folder / 'inspector.py') == meta['inspector_source_SHA256']
                and sha(folder / 'function-region.private.bin') == meta['region']['SHA256']
                and all(x['SHA256'] == parts[0]['SHA256'] for x in meta['cache_parts_read']), 'internal bounded capture identity')
    return {'status': 'PASS', 'scope': 'Evidence audit; hardware codec execution still fails',
        'native_processes_terminal': len(rows), 'nonoverlapping': True, 'codecs': counts,
        'M1_CPU_reference_processes': 3, 'M1_GPU_execution': False,
        'MPEG2_fixture': {'frames': 6, 'compressed_bytes': len(data),
            'compressed_SHA256': reference['compressed_SHA256'], 'decoded_bytes': len(pixels),
            'decoded_SHA256': reference['decoded_SHA256'], 'ffmpeg_SHA256': reference['ffmpeg_SHA256'],
            'ffprobe_SHA256': reference['ffprobe_SHA256'], 'generator_SHA256': transfer['source_SHA256']},
        'observed_native_policy_calls_on_configuring_thread': 0,
        'static_selection_analysis': {'VT_UUID': capture['image_UUID'],
            'public_create_wrapper_bytes': 26, 'implementation_bytes': 6538,
            'implementation_SHA256': load(results / 'video-codec-create-implementation-20261016/metadata.json')['region']['SHA256'],
            'runtime_error_branch_proved': False, 'private_ABI_invoked': False},
        'host_private_query_calls': 0, 'hardware_video_execution_proved': False,
        'global_failure_root_cause_proved': False, 'system_files_unchanged': 83,
        'additional_policy_file_unchanged': 1, 'OCLP_unchanged': True, 'common_runtime_sources_unchanged': 36,
        'Qwen_job_ids': [], 'system_deployment': 'NOT RUN', 'performance_benchmark': 'NOT RUN',
        'full_objective_complete': False, 'processes': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('New audit destination required')
    result = audit(args.lab_root.resolve())
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'native_processes_terminal', 'codecs',
        'observed_native_policy_calls_on_configuring_thread', 'hardware_video_execution_proved')}))


if __name__ == '__main__':
    main()
