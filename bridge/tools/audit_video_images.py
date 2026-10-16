#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recalculate the recorded dyld/AppleVA experiment, without running GPU work.

Requires the original private laboratory receipts and reference pixels. Neither
vendor code, disassembly, raw images nor local paths are emitted in the summary.
Availability-query success is deliberately distinct from working video decode.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import plistlib

from verify_native_control_reserve import terminal, require

AVA = '/System/Library/PrivateFrameworks/AppleVA.framework/Versions/A/AppleVA'
AVA_UUID = '7533f7872ca53a968dc5fa34f9035e37'
VT = '/System/Library/Frameworks/VideoToolbox.framework/Versions/A/VideoToolbox'
VT_UUID = 'e7231bea63883d0a95c0a93ce970b96b'
POLICY_SHA = 'e5cff89218a12c5a55b35832f13fa9552c1990d8f8100a68a7e9f0848fbfb0dc'


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def catalog(snapshot):
    require(all(snapshot[k] == 0 for k in ('dropped', 'invalid', 'not_ready')), 'catalogue incomplete')
    require(snapshot['added'] == len(snapshot['images']) and not snapshot['UUID_is_file_SHA256'], 'image count or UUID claim')
    for name, uuid, version in [(AVA, AVA_UUID, '5.1.1'), (VT, VT_UUID, '3330.13.105')]:
        matches = [r for r in snapshot['images'] if r['install_name'] == name and r['alive']]
        require(len(matches) == 1 and matches[0]['UUID'] == uuid
                and matches[0]['current_version'] == version, 'loaded image identity')
    require(not any('AppleGVA.framework/' in r['path'] for r in snapshot['images']), 'unexpected GVA image')


def audit(lab):
    results = lab / 'results'
    progress = results / 'video-images-progress-20261016'
    rows, receipts = [], []

    def receipt(name, build):
        root = results / name
        inputs = terminal(root, lab, results / build)
        require(inputs == load(results / build / 'inputs.json'), 'build input identity')
        m = load(root / 'execution/manifest.json')
        receipts.append(m)
        rows.append({'cohort': name, 'mode': m['arguments'][-1], 'process_terminal': True,
                     'result_SHA256': sha(root / 'results.json'),
                     'manifest_SHA256': sha(root / 'execution/manifest.json')})
        return root, load(root / 'results.json')

    image_cases = [
        ('video-images-catalog-20261016', 'video-images-build-20261016'),
        *[('video-images-' + n + '-20261016-02', 'video-images-build-20261016-02')
          for n in ['catalog', 'selftest', 'vt-cpu', 'vt-observe', 'vda-observe']]]
    cpu_bytes = 0
    for name, build in image_cases:
        root, d = receipt(name, build)
        images = load(root / 'images.json')
        for snapshot in [images['before'], images['after'], images['final']]:
            catalog(snapshot)
        for phase in ('before', 'after'):
            symbols = images['existing_GVA_symbols_' + phase]
            require(len(symbols) == 5 and all(not x['invoked'] and not x['found']
                    and not x['existing_GVA_handle'] for x in symbols), 'no-load GVA lookup')
        mode = images['mode']
        if mode == 'catalog':
            c = images['calibration']
            require(c['enabled'] and c['value'] == 37 and c['dlclose_status'] == 0, 'CPU fixture calibration')
            require((images['before']['active'], c['loaded']['active'], c['unloaded']['active'])
                    == (349, 350, 349), 'calibration load/remove')
            require(images['final']['removed'] == 1, 'missing removal callback')
        elif mode == 'selftest':
            require(d['integer_ABI_cases'] == d['floating_ABI_cases'] == 128
                    and d['observer']['create_calls'] == d['observer']['destroy_calls'] == 128,
                    'synthetic ABI results')
        elif mode == 'vt-cpu':
            require(d['output_frames'] == 6 and d['CPU_reference_bytes_compared'] == 691200
                    and d['missing_CPU_references'] == d['different_bytes'] == 0
                    and d['decode']['specification'] == {'EnableHardwareAcceleratedVideoDecoder': False}, 'CPU decode control')
            concatenated = bytearray()
            for i, filename in enumerate(d['frame_files']):
                actual = (root / 'outputs' / filename).read_bytes()
                reference = (root / 'assets/fixture' / ('cpu-frame-%03d.nv12' % i)).read_bytes()
                require(len(actual) == 115200 and actual == reference, 'independent frame bytes')
                concatenated.extend(actual)
            require(hashlib.sha256(concatenated).hexdigest()
                    == 'd73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1', 'independent reference identity')
            cpu_bytes = len(concatenated)
        elif mode == 'vt-observe':
            require(d['decode']['create_status'] == -12906 and d['output_frames'] == 0
                    and d['decode']['specification'] == {'RequireHardwareAcceleratedVideoDecoder': True}, 'VT hardware failure')
        elif mode == 'observe':
            require(d['create_status'] == -12473 and not d['hardware_frames_produced'], 'VDA failure')
        else:
            raise ValueError('Unknown cohort mode')

    build = 'video-policy-build-20261016'
    policy_cases = [('inspect', ''), ('native', ''), ('wrong-model', ''), ('model-entry', '')]
    policy_cases += [(m, '-r' + str(i)) for i in (2, 3) for m in ['native', 'wrong-model', 'model-entry']]
    policy_cases += [('native', '-after')]
    profile = load(progress / 'VP3-query-profile.json')
    pins = [{k: p[k] for k in ('offset', 'bytes', 'SHA256')} for p in profile['functions']]
    counts = {'native': 0, 'wrong-model': 0, 'model-entry': 0}
    for mode, repeat in policy_cases:
        root, d = receipt('video-policy-' + mode + repeat + '-20261016', build)
        require(d['mode'] == mode and d['model'] == 'iMac11,1' and d['image_UUID'] == AVA_UUID
                and d['resident_code_pins'] == pins, 'resident query profile')
        require(not any(d[k] for k in ('unknown_private_factory_or_decoder_invoked',
                'hardware_video_execution_proved', 'system_modified', 'performance_benchmark')), 'query scope')
        require(d['policy_SHA256_before'] == d['policy_SHA256_after'] == POLICY_SHA, 'policy changed')
        trace = d['policy']
        require(trace['dropped'] == 0 and trace['configuring_thread_only'] and trace['disabled_before_snapshot']
                and not trace['system_file_modified'] and not trace['driver_instructions_modified'], 'observer scope')
        if mode == 'inspect':
            require(not d['known_private_query_invoked'] and d['query_status'] is None and not trace['events'], 'inspect invoked code')
        else:
            expected = 0 if mode == 'model-entry' else -8973
            require(d['known_private_query_invoked'] and d['query_status'] == expected
                    and d['calibration_model_entry_present'] == (mode == 'model-entry'), 'query outcome')
            events = trace['events']
            require(len(events) == 2 and sum(e['synthetic_calibration'] for e in events) == 1
                    and sum(e['pinned_native_callsite'] for e in events) == 1, 'query callsite evidence')
            require(all(e['original_success'] and e['original_data_hash_verified']
                    and e['return_data_changed'] == (mode != 'native') for e in events), 'data replacement evidence')
            native = next(e for e in events if e['pinned_native_callsite'])
            require(native['caller_image'] == AVA and native['caller_offset'] == 267793
                    and not native['synthetic_calibration'], 'native caller')
            counts[mode] += 1
        for phase in ('before', 'after'):
            catalog(load(root / 'images.json')[phase])
    require(counts == {'native': 4, 'wrong-model': 3, 'model-entry': 3}, 'query cohort count')
    for mode, model in [('model-entry', 'iMac11,1'), ('wrong-model', 'KeplerMetal-Control-NoMatch')]:
        overlay = plistlib.loads((results / build / 'assets' / (mode + '.plist')).read_bytes())
        require(overlay == {'System Support': {model: {'boostIG': False, 'disallowBGRA': False}}}, 'overlay content')

    ordered = sorted(receipts, key=lambda r: r['started_at'])
    for before, after in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(before['completed_at']) <=
                datetime.datetime.fromisoformat(after['started_at']), 'overlapping cohorts')
    start = load(progress / 'start.json')
    require(len(start['system_before']) == 83, 'protected inventory count')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'protected system file changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256'], 'OCLP changed')
    require(sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == POLICY_SHA, 'system policy changed')
    runtime = load(results / 'native-allocation-runtime-build-20261016-04/manifest.json')
    require(len(runtime['source_SHA256']) == 36, 'common source inventory')
    for name, digest in runtime['source_SHA256'].items():
        require(sha(lab / name) == digest, 'common runtime source changed')

    captured = results / 'video-cache-AppleVA-VP3-20261016'
    manifest = load(captured / 'capture.json')
    require(manifest['image_UUID'] == AVA_UUID and not manifest['vendor_program_executed'], 'static capture identity')
    for name, digest in manifest['source_hashes'].items():
        require(sha(captured / name) == digest, 'frozen cache inspector')
    parts = manifest['cache_parts_read']
    require(len(parts) == 1 and parts[0]['UUID'] == '8b9bd562bd153d14a8b6343e9b14535b'
            and sha(parts[0]['path']) == parts[0]['SHA256'], 'cache full-file identity')
    for row in manifest['records']:
        folder = captured / row['folder']
        require(sha(folder / 'metadata.json') == row['metadata_SHA256']
                and sha(folder / 'function-region.private.bin') == row['region_SHA256'], 'named function capture')
    helpers = results / 'video-cache-AppleVA-helpers-20261016'
    analysis = load(helpers / 'analysis.json')
    require(analysis['image_UUID'] == AVA_UUID and sha(helpers / 'inspector.py') == analysis['inspector_SHA256'], 'helper inspector')
    for row in analysis['records']:
        require(sha(helpers / row['folder'] / 'function-region.private.bin') == row['region_SHA256'], 'helper capture')
    require(manifest['records'][0]['region_SHA256'] == pins[0]['SHA256']
            and all(analysis['records'][i]['region_SHA256'] == pins[i + 1]['SHA256'] for i in (0, 1)), 'resident/offline equality')
    return {'status': 'PASS', 'native_processes_terminal': len(receipts), 'nonoverlapping': True,
        'new_synthetic_ABI_cases': 256, 'CPU_control_frames': 6, 'CPU_reference_bytes': cpu_bytes,
        'CPU_different_bytes': 0, 'hardware_only_VT_create_status': -12906, 'VDA_create_status': -12473,
        'AppleVA_UUID': AVA_UUID, 'AppleVA_version': '5.1.1', 'VT_UUID': VT_UUID, 'VT_version': '3330.13.105',
        'eligibility_query': {'inspections_without_invocation': 1, 'native_refusals': counts['native'],
            'wrong_model_refusals': counts['wrong-model'], 'model_entry_successes': counts['model-entry'],
            'refusal_status': -8973, 'success_status': 0, 'resident_code_pins': pins,
            'system_policy_SHA256': POLICY_SHA, 'system_policy_unchanged': True},
        'system_files_unchanged': 83, 'additional_policy_file_unchanged': 1, 'OCLP_unchanged': True,
        'common_runtime_sources_unchanged': 36, 'shared_cache_file_SHA256': parts[0]['SHA256'],
        'new_M1_execution': False, 'Qwen_job_ids': [], 'hardware_video_execution_proved': False,
        'global_H264_failure_explained': False, 'system_deployment': 'NOT RUN', 'performance_benchmark': 'NOT RUN',
        'full_objective_complete': False, 'processes': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Audit destination already exists')
    result = audit(args.lab_root.resolve())
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'native_processes_terminal',
        'CPU_reference_bytes', 'eligibility_query', 'hardware_video_execution_proved')}))


if __name__ == '__main__':
    main()
