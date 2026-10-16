#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the recorded registry experiment, without native or GPU execution.

Raw object descriptions, pointers, pixels and vendor code stay in the lab.
The returned report contains selected identifiers, scalar counts and hashes.
Debug CF descriptions are evidence for this pinned cohort, not a stable parser
contract for other OS versions or a production decoder-selection mechanism.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import plistlib
import re

from verify_native_control_reserve import terminal


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inputs(root):
    data = load(root / 'inputs.json')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            require(sha(root / folder / name) == digest, 'build input changed: ' + name)
    for name, digest in data.get('object_SHA256', {}).items():
        require(sha(root / name) == digest, 'object changed: ' + name)
    for variant, digest in data['executable_variants_SHA256'].items():
        require(sha(root / ('application-' + variant)) == digest, 'variant changed')
    require(not data['GPU_execution'] and not data['private_function_invoked_by_host'], 'build scope')
    require(all(c['exit_code'] == 0 for c in load(root / 'commands.json')), 'failed qualified build')
    return data


def oracle(mode, seed, trial):
    if mode in ('integer', 'overflow', 'disabled'):
        value = 0
        for i, weight in enumerate((1, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)):
            value ^= (seed + i) * weight
        return value
    if mode == 'floating':
        return sum((i + 1) * (seed + i) / 2 for i in range(10))
    if mode == 'aggregate':
        return [sum(w * (seed + i) for i, w in enumerate((1, 3, 5, 7))),
                (seed + 4) ^ (11 * (seed + 5)) ^ (13 * (seed + 6)) ^ (17 * (seed + 7)),
                8 * seed + 28]
    if mode == 'mixed':
        return [sum(w * (seed + i) for i, w in enumerate((1, 3, 5, 7, 11, 13, 17))),
                seed / 2 + 3 * (seed + 1) / 2 + 5 * (seed + 2) / 2 + (seed ^ (seed + 6)) / 2]
    if mode == 'variadic':
        value = seed
        for i in range(6):
            value ^= (seed + 3 * i) * (i + 1)
            value += (seed + 5 * i) * (i + 3)
        return value
    if mode == 'flags':
        return sum(1 << bit for i, bit in enumerate((0, 2, 4, 6, 7, 11)) if trial & (1 << i))
    raise ValueError('unknown calibration mode')


def correlate(trace, metadata):
    """Require a complete per-stack/index bijection before associating objects."""
    raw, retained = defaultdict(list), defaultdict(list)
    for event in trace['events']:
        if event['index'] in (1, 3):
            raw[event['index'], event['entry_stack']].append(event)
    for event in metadata['events']:
        if not event['synthetic_control']:
            retained[event['private_entry_index'], event['source_entry_stack']].append(event)
    require(set(raw) == set(retained), 'metadata entry-stack groups differ')
    pairs = []
    for key in raw:
        require(len(raw[key]) == len(retained[key]), 'ambiguous metadata correlation')
        pairs.extend(zip(raw[key], retained[key]))
    return pairs


def audit(lab):
    lab = lab.resolve()
    results, progress = lab / 'results', lab / 'results/video-registry-progress-20261016'
    base = results / 'video-registry-build-20261016'
    meta = results / 'video-registry-metadata-build-20261016'
    spec = results / 'video-registry-spec-build-20261016-02'
    bi, mi, si = inputs(base), inputs(meta), inputs(spec)
    references = {
        'H264': (results / 'video-va-observer-build-20261016-05/assets/fixture',
                 'd73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1'),
        'MPEG2Video': (results / 'video-codec-policy-progress-20261016/M1-mpeg2-return/fixture',
                 '882c66a3f07501919430ecf4df55cbdd0947af2448de2892bfb3c969866b8dee')}
    for codec, (original, digest) in references.items():
        require(len(list(original.iterdir())) == 13, 'reference fixture count')
        for file in original.iterdir():
            require(sha(base / 'assets/fixtures' / codec / file.name) == sha(file), 'reference staging changed')
        pixels = b''.join(file.read_bytes() for file in sorted(original.glob('cpu-frame-*.nv12')))
        require(len(pixels) == 691200 and hashlib.sha256(pixels).hexdigest() == digest, 'independent reference pin')
    for kind, digest in bi['library_SHA256'].items():
        require(sha(base / ('libVideoRegistry-' + kind + '.dylib')) == digest, 'base library changed')
    require(Path(mi['base_build']) == base and mi['base_inputs_SHA256'] == sha(base / 'inputs.json'), 'metadata base')
    require(mi['qualified_entry_library_SHA256'] == bi['library_SHA256']['observer']
            == sha(mi['qualified_entry_library']), 'qualified entry library')
    require(mi['qualified_tail_object_SHA256'] == bi['object_SHA256']['tail.o'], 'qualified tail object')
    require(mi['reused_host_object_SHA256'] == bi['object_SHA256']['codec-host.o']
            == sha(meta / 'base-codec-host.o'), 'host not exactly reused')
    require(mi['reused_catalog_object_SHA256'] == bi['object_SHA256']['catalog.o']
            == sha(meta / 'base-catalog.o'), 'catalog not exactly reused')
    require(sha(meta / 'libVideoRegistryMetadata.dylib') == mi['metadata_library_SHA256'], 'metadata library')
    require(si['metadata_inputs_SHA256'] == sha(meta / 'inputs.json')
            and Path(si['metadata_build']) == meta
            and si['qualified_metadata_library_SHA256'] == mi['metadata_library_SHA256']
            and si['qualified_entry_library_SHA256'] == mi['qualified_entry_library_SHA256'], 'spec build reuse')
    for kind, digest in si['specification_library_SHA256'].items():
        require(sha(spec / ('libVideoRegistrySpec-' + kind + '.dylib')) == digest, 'spec library')

    profile = load(progress / 'registry-profile.json')
    require(profile['UUID'] == '7c4ae5aed528396982c6a4a534949ef3'
            and profile['version'] == '3330.13.105' and len(profile['symbols']) == 6, 'CoreMedia identity')
    inspection = load(progress / 'tail-object-inspection.json')
    require(inspection['exit_code'] == 0 and len(inspection['function_labels']) == 6
            and not inspection['call_instructions']
            and inspection['tail_object_SHA256'] == sha(base / 'tail.o')
            and inspection['listing_SHA256'] == sha(progress / 'tail-object-disassembly.txt'), 'tail inspection')
    receipts, rows = [], []

    def receipt(name, build):
        root = results / name
        actual = terminal(root, lab, build)
        expected = load(build / 'inputs.json')
        require(all(actual[k] == v for k, v in expected.items()), 'recorded build mismatch')
        variant = actual.get('selected_variant', actual.get('selected_codec'))
        require(actual['executable_SHA256'] == expected['executable_variants_SHA256'][variant], 'variant identity')
        d = load(root / 'results.json')
        for key in ('direct_unknown_private_call', 'system_modified', 'performance_benchmark', 'hardware_video_execution_proved'):
            require(d[key] is False, 'experiment scope: ' + key)
        t = d['trace']
        require(t['recorders_drained'] and t['disabled_before_snapshot'] and not t['pending'], 'trace incomplete')
        for key in ('original_instructions_modified', 'arguments_modified', 'original_return_address_replaced',
                    'opaque_argument_pointers_dereferenced', 'thread_ids_recorded'):
            require(t[key] is False, 'entry observer scope: ' + key)
        require([e['ordinal'] for e in t['events']] == list(range(len(t['events']))), 'trace order')
        require(all(e['entry_stack'] % 16 == 8 for e in t['events']), 'entry stack alignment')
        m = load(root / 'execution/manifest.json')
        receipts.append(m)
        row = {'case': name, 'PID': m['pid'], 'result_SHA256': sha(root / 'results.json'),
               'inputs_SHA256': sha(root / 'inputs.json'), 'entry_calls': t['calls'], 'entry_dropped': t['dropped']}
        rows.append(row)
        return root, d, row

    total = 0
    for mode in ('integer', 'floating', 'aggregate', 'mixed', 'variadic', 'flags', 'overflow', 'disabled'):
        root, d, row = receipt('video-registry-calibration-' + mode + '-20261016', base)
        count = 1027 if mode == 'overflow' else 384
        require(d['status'] == 'PASS' and d['mode'] == mode and d['library_kind'] == 'calibration'
                and d['verified_calls'] == count == len(d['cases']) and d['case_failures'] == 0
                and d['bounded_trace_valid'], 'calibration result')
        for n, case in enumerate(d['cases']):
            index, trial = (0, n) if mode == 'overflow' else divmod(n, 64)
            seed = 0x13579 + index * 991 + trial * 17
            expected = oracle(mode, seed, trial)
            actual = case['actual'] & 0x8d5 if mode == 'flags' else case['actual']
            require(case['index'] == index and case['trial'] == trial and case['seed'] == seed
                    and actual == expected and case['correct'], 'independent calibration oracle')
        trace = d['trace']
        require(trace['calls'] == (0 if mode == 'disabled' else count)
                and trace['dropped'] == (3 if mode == 'overflow' else 0)
                and len(trace['events']) == (0 if mode == 'disabled' else min(count, 1024)), 'bounded calibration')
        if mode not in ('overflow', 'disabled'):
            require(Counter(e['index'] for e in trace['events']) == {i: 64 for i in range(6)}, 'six tails')
        for event in trace['events']:
            case = d['cases'][event['ordinal']]
            seed, trial = case['seed'], case['trial']
            args = event['raw_integer_arguments']
            if mode in ('integer', 'overflow'):
                require(args == list(range(seed, seed + 6)), 'integer arguments')
            elif mode == 'aggregate':
                require(args[1:] == list(range(seed, seed + 5)), 'hidden sret and integer arguments')
            elif mode == 'mixed':
                require(args == list(range(seed, seed + 6)), 'mixed integer arguments')
            elif mode == 'variadic':
                require(args == [seed, seed, seed + 3, seed + 6, seed + 9, seed + 12]
                        and event['incoming_RAX'] & 255 == 6, 'variadic integer/AL arguments')
            elif mode == 'flags':
                require(event['arithmetic_flags'] & 0x8d5 == oracle(mode, seed, trial), 'condition flags')
        row['independent_CPU_cases'] = count
        total += count
    require(total == 3715, 'synthetic cohort count')

    inspected, d, row = receipt('video-registry-inspect-20261016', base)
    require(d['mode'] == 'inspect' and d['public_decode'] is None and d['trace']['calls'] == 0
            and d['resident_code_pins'] == profile['symbols'], 'inspection executed decode')
    CPU_frames = CPU_bytes = hardware_failures = retained_objects = 0
    selections, specs = [], []

    def codec_case(name, build, codec, mode, observer=True, metadata=False, specification=None):
        nonlocal CPU_frames, CPU_bytes, hardware_failures, retained_objects
        root, d, row = receipt(name, build)
        t, decoded = d['trace'], d['public_decode']
        require(d['codec'] == codec and d['mode'] == mode and d['resident_code_pins'] == profile['symbols']
                and t['dropped'] == 0, 'codec identity')
        require(not decoded['hardware_video_execution_proved'] and not decoded['system_modified']
                and not decoded['performance_benchmark'] and decoded['fixture_samples'] == 6, 'decode scope')
        status = decoded['decode']['create_status']
        if mode == 'cpu':
            require(status == 0 and decoded['output_frames'] == 6 and decoded['different_bytes'] == 0
                    and decoded['missing_CPU_references'] == 0 and decoded['CPU_reference_bytes_compared'] == 691200
                    and decoded['decode']['decode_status'] == [0] * 6
                    and decoded['decode']['wait_status'] == decoded['decode']['finish_status'] == 0, 'CPU decode')
            require(len(decoded['frame_files']) == 6, 'CPU frames')
            for index, filename in enumerate(decoded['frame_files']):
                require(filename == 'vt-frame-%03d.nv12' % index, 'frame path')
                actual = (root / 'outputs' / filename).read_bytes()
                ref = (root / 'assets/fixtures' / codec / ('cpu-frame-%03d.nv12' % index)).read_bytes()
                require(actual == ref and len(ref) == 115200, 'pixel CPU oracle')
                CPU_bytes += len(ref)
            CPU_frames += 6
        else:
            require(status == -12906 and decoded['output_frames'] == 0 and not decoded['frame_files']
                    and decoded['CPU_reference_bytes_compared'] == 0
                    and decoded['decode']['specification'] == {'RequireHardwareAcceleratedVideoDecoder': True}, 'hardware failure')
            require(not list((root / 'outputs').glob('vt-frame-*.nv12')), 'unexpected hardware frame')
            hardware_failures += 1
        expected_counts = [0, 42, 0, 41, 1, 1] if mode == 'cpu' else (
            [1, 45, 0, 41, 0, 0] if codec == 'H264' else [1, 39, 0, 39, 0, 0])
        if observer and specification is None:
            require(Counter(e['index'] for e in t['events']) == {i: n for i, n in enumerate(expected_counts) if n}, 'entry counts')
        elif not observer:
            require(t['calls'] == 0 and not t['events'], 'plain library intercepted')
        errors = [e for e in t['events'] if e['index'] == 0]
        if observer:
            require(len(errors) == (mode == 'hardware'), 'error trace count')
            if errors:
                e = errors[0]
                raw = e['raw_integer_arguments'][2] & 0xffffffff
                require(raw - (1 << 32) == -12906 and e['caller_offset'] == 20163
                        and e['caller_image'].endswith('/VideoToolbox'), 'bounded error evidence')
        row.update(codec=codec, mode=mode, create_status=status, frames=decoded['output_frames'])
        if metadata:
            m = load(root / 'metadata.json')
            require(m == load(root / 'outputs/metadata.json') and m['status'] == 'COMPLETE'
                    and m['recorders_drained'] and m['disabled_before_snapshot']
                    and not m['pending'] and not m['dropped'] and m['public_retain_control_valid'], 'metadata completeness')
            for key in ('returned_objects_or_ownership_modified', 'system_modified', 'opaque_registry_items_dereferenced',
                        'private_entry_invoked_directly', 'description_format_is_stable_API'):
                require(m[key] is False, 'metadata scope: ' + key)
            synthetic = [e for e in m['events'] if e['synthetic_control']]
            require(len(synthetic) == 1 and 'KeplerMetal retain control' in synthetic[0]['description'], 'retain lifetime control')
            require(m['calls'] == len(m['events']) and all(e['description_present'] and not e['truncated']
                    and e['CF_type'] == 18 and e['characters'] == e['characters_copied'] for e in m['events']), 'CF object captures')
            require([e['ordinal'] for e in m['events']] == list(range(m['calls'])), 'metadata record order')
            pairs = correlate(t, m)
            require(len(pairs) + 1 == m['calls'], 'metadata bijection size')
            for raw, event in pairs:
                require(event['caller_offset'] == {1: 118143, 3: 118188}[raw['index']]
                        and event['caller_image'] == profile['module'], 'public retain site')
            retained_objects += len(pairs)
            wanted = ('avc.vcp', 'avd.avc', 'h264.gva', 'mpeg2')
            descriptions = {}
            selected = defaultdict(list)
            for raw, event in pairs:
                text = event['description']
                if raw['index'] != 3:
                    continue
                match = re.search(r'CMClassImplementationID = "([^"]+)";', text)
                if match and any(match[1].endswith('.' + x) for x in wanted):
                    descriptions[match[1]] = text
                    selected[match[1]].append(raw['caller_offset'])
            require(len(descriptions) == 4, 'expected relevant descriptor observations')
            gva = descriptions['com.apple.videotoolbox.videodecoder.h264.gva']
            require('IORegistryRequiredKey = IOGVACodec;' in gva
                    and 'EnableHardwareAcceleratedVideoDecoder = 1;' in gva
                    and 'VTIsHardwareAccelerated = 1;' in gva, 'GVA registration requirements')
            require('VTIsHardwareAccelerated = 0;' in descriptions['com.apple.videotoolbox.videodecoder.mpeg2'], 'software MPEG2 descriptor')
            selections.append({'case': name, 'metadata_events': m['calls'], 'metadata_SHA256': sha(root / 'metadata.json'),
                'correlated_objects': len(pairs), 'relevant_description_caller_offsets': dict(selected)})
        if specification is not None:
            s = load(root / 'specification.json')
            expected_applied = specification == 'both' and mode == 'hardware'
            before = ({'RequireHardwareAcceleratedVideoDecoder': True} if mode == 'hardware'
                      else {'EnableHardwareAcceleratedVideoDecoder': False})
            after = {**before, 'EnableHardwareAcceleratedVideoDecoder': True} if expected_applied else before
            require(s == load(root / 'outputs/specification.json') and s['status'] == 'PUBLIC_API_RETURNED'
                    and s['applied'] == expected_applied and s['hardware_requirement_preserved']
                    and s['original_specification'] == before and s['forwarded_specification'] == after
                    and s['create_status'] == status and not s['system_modified'] and not s['performance_benchmark'], 'public specification forwarding')
            specs.append({'case': name, 'applied': s['applied'], 'forwarded_specification': after,
                          'create_status': status, 'frames': decoded['output_frames'], 'SHA256': sha(root / 'specification.json')})

    for codec in ('H264', 'MPEG2Video'):
        for kind in ('plain', 'observer'):
            for mode in ('cpu', 'hardware'):
                codec_case('video-registry-' + codec + '-' + kind + '-' + mode + '-20261016', base,
                           codec, mode, observer=kind == 'observer')
        for mode in ('cpu', 'hardware'):
            codec_case('video-registry-metadata-' + codec + '-' + mode + '-20261016', meta,
                       codec, mode, metadata=True)
    for codec, kind, mode in [('H264', 'passive', 'hardware'), ('H264', 'both', 'cpu'),
                              ('H264', 'both', 'hardware'), ('MPEG2Video', 'both', 'hardware')]:
        codec_case('video-registry-spec-' + codec + '-' + kind + '-' + mode + '-20261016', spec,
                   codec, mode, metadata=True, specification=kind)

    ordered = sorted(receipts, key=lambda row: row['started_at'])
    for earlier, later in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(earlier['completed_at']) <=
                datetime.datetime.fromisoformat(later['started_at']), 'overlapping native cohort')
    require(len(receipts) == 25 and CPU_frames == 42 and CPU_bytes == 4838400
            and hardware_failures == 9, 'cohort totals')
    observations = load(progress / 'IOGVA-key-observation.json')
    require(len(observations) == 6 and all(r['exit_code'] == 0 and r['matches'] == [] for r in observations), 'IORegistry key observation')
    for row in observations:
        raw = (progress / ('ioreg-' + row['key'] + '.plist')).read_bytes()
        # ioreg -a emits zero bytes when no service matches the key. A nonempty
        # result must still be a valid empty plist, never an ignored parse error.
        require(raw == b'' or plistlib.loads(raw) == [], 'IORegistry raw evidence')

    capture_root = results / 'video-registry-CoreMedia-cache-20261016'
    capture = load(capture_root / 'capture.json')
    require(capture['image_UUID'] == profile['UUID'] and not capture['vendor_program_executed'], 'static capture scope')
    for name, digest in capture['source_hashes'].items():
        require(sha(capture_root / name) == digest, 'cache inspector source')
    for index, entry in enumerate(capture['records']):
        folder = capture_root / entry['folder']
        require(sha(folder / 'metadata.json') == entry['metadata_SHA256']
                and sha(folder / 'function-region.private.bin') == entry['region_SHA256']
                == profile['symbols'][index]['SHA256'], 'static/resident code equality')
    require(len(capture['cache_parts_read']) == 1, 'cache part count')
    cache = capture['cache_parts_read'][0]
    require(cache['UUID'] == '8b9bd562bd153d14a8b6343e9b14535b'
            and sha(cache['path']) == cache['SHA256'], 'whole cache identity')
    start = load(progress / 'start.json')
    require(len(start['system_before']) == 83, 'protected inventory')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'protected file changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256'], 'OCLP changed')
    require(sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == start['policy_SHA256'], 'video policy changed')
    runtime = load(results / 'native-allocation-runtime-build-20261016-04/manifest.json')
    require(len(runtime['source_SHA256']) == 36, 'common runtime source count')
    for name, digest in runtime['source_SHA256'].items():
        require(sha(lab / name) == digest, 'common runtime source changed')
    return {'status': 'PASS', 'auditor_SHA256': sha(__file__),
        'native_processes_terminal': len(receipts), 'nonoverlapping': True,
        'independent_known_CPU_ABI_cases': total, 'expected_saturation_drops': 3,
        'CPU_control_frames': CPU_frames, 'CPU_reference_bytes': CPU_bytes, 'CPU_different_bytes': 0,
        'hardware_required_failures': hardware_failures, 'hardware_create_status': -12906,
        'CoreMedia_UUID': profile['UUID'], 'CoreMedia_version': profile['version'], 'resident_code_pins': profile['symbols'],
        'shared_tail_object_SHA256': sha(base / 'tail.o'), 'host_object_exactly_reused': True,
        'retained_objects_correlated': retained_objects, 'metadata': selections, 'specification_experiment': specs,
        'missing_IORegistry_keys': [row['key'] for row in observations], 'missing_key_causal_test': 'NOT RUN',
        'error_signal_VT_return_offset': 20163, 'get_factory_interposed_calls': 0,
        'unobserved_direct_or_cached_calls_excluded': False, 'system_files_unchanged': 83,
        'additional_policy_file_unchanged': 1, 'OCLP_unchanged': True, 'common_runtime_sources_unchanged': 36,
        'shared_cache_SHA256': cache['SHA256'], 'new_M1_execution': False, 'Qwen_job_ids': [],
        'system_deployment': 'NOT RUN', 'performance_benchmark': 'NOT RUN', 'hardware_video_execution_proved': False,
        'full_objective_complete': False, 'processes': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Audit destination exists')
    result = audit(args.lab_root)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'native_processes_terminal', 'independent_known_CPU_ABI_cases',
        'CPU_control_frames', 'CPU_reference_bytes', 'hardware_required_failures', 'hardware_video_execution_proved')}))


if __name__ == '__main__':
    main()
