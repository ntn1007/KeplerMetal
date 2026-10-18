#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the recorded native GPU dependency experiment without dispatching work.

PASS qualifies the bounded observations and counterfactual's scope. The actual
hardware decoder still fails; no engine execution or deployment is certified.
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
from verify_native_control_reserve import terminal


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def build_inputs(root, parent):
    d = load(root / 'inputs.json')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in d[key].items():
            require(sha(root / folder / name) == digest, 'frozen build input: ' + name)
    require(len(load(root / 'commands.json')) == 13
            and all(c['exit_code'] == 0 for c in load(root / 'commands.json')), 'build completion')
    for kind, digest in d['dependency_libraries_SHA256'].items():
        require(sha(root / ('libVideoDependency-' + kind + '.dylib')) == digest, 'dependency library')
    for variant, digest in d['executable_variants_SHA256'].items():
        require(sha(root / ('application-' + variant)) == digest, 'frozen executable variant')
    require(Path(d['metadata_build']) == parent and d['metadata_inputs_SHA256'] == sha(parent / 'inputs.json'), 'qualified parent')
    pi = load(parent / 'inputs.json')
    require(d['qualified_entry_library_SHA256'] == pi['qualified_entry_library_SHA256']
            == sha(pi['qualified_entry_library']) and d['qualified_metadata_library_SHA256']
            == pi['metadata_library_SHA256'] == sha(parent / 'libVideoRegistryMetadata.dylib'), 'qualified libraries reused')
    require(d['reused_host_object_SHA256'] == sha(parent / 'base-codec-host.o') == pi['reused_host_object_SHA256']
            and d['reused_catalog_object_SHA256'] == sha(parent / 'base-catalog.o')
            == pi['reused_catalog_object_SHA256'], 'qualified host/catalog reuse')
    for codec, digest in d['reused_decoder_objects_SHA256'].items():
        require(sha(parent / (codec + '.o')) == digest == pi['object_SHA256'][codec + '.o'], 'qualified decoder reuse')
    require(not d['GPU_execution'] and not d['unknown_private_function_invoked_by_host'], 'build scope')
    return d


def audit(lab):
    lab = lab.resolve()
    results, progress = lab / 'results', lab / 'results/video-dependency-progress-20261018'
    b1, b2 = results / 'video-dependency-build-20261016', results / 'video-dependency-build-20261018-02'
    parent = results / 'video-registry-metadata-build-20261016'
    i1, i2 = build_inputs(b1, parent), build_inputs(b2, parent)
    profile = load(progress / 'dependency-profile.json')
    pins = [{k: row[k] for k in ('offset', 'bytes', 'SHA256')} for row in profile['functions']]
    CM_pins = load(results / 'video-registry-progress-20261016/registry-profile.json')['symbols']
    require(profile['UUID'] == 'e7231bea63883d0a95c0a93ce970b96b'
            and profile['version'] == '3330.13.105' and profile['GPU_registry_ID'] == 4294968458
            and profile['IORegistry_search_return_offset'] == 6285217, 'VT/GPU profile')
    rows, manifests, counterfactual = [], [], []
    CPU_frames = CPU_bytes = real_queries = query_controls = metadata_objects = scope_cases = hardware_failures = 0

    def receipt(name, build, expected_variant, mode, choice='native', v2=False):
        nonlocal CPU_frames, CPU_bytes, real_queries, query_controls, metadata_objects, scope_cases, hardware_failures
        root = results / name
        run = terminal(root, lab, build)
        frozen = load(build / 'inputs.json')
        require(run['selected_variant'] == expected_variant and run['executable_SHA256']
                == frozen['executable_variants_SHA256'][expected_variant], 'executed variant')
        for key, value in frozen.items():
            if key != 'assets_SHA256':
                require(run[key] == value, 'run/build provenance: ' + key)
        for name_, digest in frozen['assets_SHA256'].items():
            if name_ != 'dependency-choice.json':
                require(run['assets_SHA256'][name_] == digest, 'changed invariant asset')
        require(set(run['assets_SHA256']) == set(frozen['assets_SHA256']), 'unexpected asset')
        if v2:
            require(load(root / 'assets/dependency-choice.json') == {'mode': choice}
                    and run['override_mode'] == choice, 'explicit experiment choice')
        d, dep = load(root / 'results.json'), load(root / 'dependency.json')
        require(dep == load(root / 'outputs/dependency.json') and dep['status'] == 'COMPLETE'
                and dep['recorders_drained'] and dep['disabled_before_snapshot'] and not dep['dropped']
                and not dep['pending'] and dep['public_query_controls_valid'], 'public observer completeness')
        require(not any(dep[k] for k in ('system_modified', 'opaque_registry_item_read', 'private_function_invoked_directly')), 'observer scope')
        require(dep['profile']['UUID'] == profile['UUID'] and dep['profile']['version'] == profile['version']
                and dep['profile']['resident_code_pins'] == pins, 'resident pins')
        if v2:
            require(dep['profile']['scope_contract_valid'] and dep['profile']['scope_contract_cases'] == 10
                    and dep['profile']['GPU_registry_ID'] == 4294968458 and not dep['return_ownership_modified']
                    and dep['counterfactual_selection'] == choice, 'counterfactual scope contract')
            scope_cases += 10
        events = dep['events']
        require(dep['calls'] == len(events) and [e['ordinal'] for e in events] == list(range(len(events)))
                and all(not e['truncated'] and e['registry_ID_status'] == 0 for e in events), 'query records')
        controls = [e for e in events if e['synthetic_control']]
        require(len(controls) == 2 and [e['key'] for e in controls]
                == ['IOKitBuildVersion', 'KeplerMetal-absent-property-control']
                and [e['result_present'] for e in controls] == [True, False]
                and all(e['class'] == 'IORegistryEntry' and e['name'] == 'Root' and e['options'] == 0
                        and e['plane'] == 'IOService' and not e['native_pinned_callsite'] for e in controls), 'positive/negative public query controls')
        query_controls += 2
        native = [e for e in events if not e['synthetic_control']]
        require(all(e['native_pinned_callsite'] and e['class'] == 'nvAccelerator' and e['name'] == 'nvAccelerator'
                    and e['registry_ID'] == 4294968458 and e['plane'] == 'IOService' and e['options'] == 1 for e in native), 'native GPU identity and site')
        observed = 'passive' not in expected_variant and mode == 'hardware' and expected_variant.startswith('H264-')
        require(Counter(e['key'] for e in native) == ({'IOGVACodec': 1, 'IOAVDHEVCDecodeCapabilities': 1} if observed else {}), 'observed query coverage')
        changed = choice == 'present-key'
        require(all(e['result_present'] == (changed and e['key'] == 'IOGVACodec') for e in native), 'query results')
        if v2:
            require(all(not e['original_result_present'] and e['return_value_changed']
                        == (changed and e['key'] == 'IOGVACodec') for e in native), 'exact replacement boundary')
            require(dep['substitutions'] == int(changed) and dep['return_value_or_ownership_modified'] == changed
                    and all(not e['return_value_changed'] for e in controls), 'replacement/control separation')
            if changed:
                # 21 is the observed type ID in this pinned cohort. The sealed
                # own source returns CFRetain(kCFBooleanTrue); it is no GPU enum.
                require(next(e for e in native if e['key'] == 'IOGVACodec')['CF_type'] == 21, 'observed public Boolean type')
        else:
            require(not dep['return_value_or_ownership_modified'], 'v1 changed a return')
        real_queries += len(native)
        m = load(root / 'execution/manifest.json')
        manifests.append(m)
        row = {'case': root.name, 'PID': m['pid'], 'result_SHA256': sha(root / 'results.json'),
            'dependency_SHA256': sha(root / 'dependency.json'), 'inputs_SHA256': sha(root / 'inputs.json'),
            'variant': expected_variant, 'mode': mode, 'choice': choice, 'native_queries': len(native)}
        rows.append(row)
        if mode == 'inspect':
            require(not dep['public_create_called'] and not native and not d['hardware_video_execution_proved'], 'inspect executed decode')
            return
        require(dep['public_create_called'] and dep['hardware_requirement_preserved'], 'public API scope')
        require(not any(d[k] for k in ('direct_unknown_private_call', 'system_modified', 'performance_benchmark', 'hardware_video_execution_proved')),
                'codec scope')
        require(d['mode'] == mode and d['resident_code_pins'] == CM_pins, 'codec resident pins')
        trace = d['trace']
        require(trace['recorders_drained'] and not trace['dropped'] and not trace['pending']
                and trace['disabled_before_snapshot'] and not trace['original_instructions_modified']
                and not trace['arguments_modified'] and not trace['opaque_argument_pointers_dereferenced'], 'entry observer invariants')
        meta = load(root / 'metadata.json')
        require(meta['status'] == 'COMPLETE' and meta['recorders_drained'] and not meta['pending']
                and not meta['dropped'] and meta['public_retain_control_valid']
                and all(not e['truncated'] for e in meta['events']), 'metadata completeness')
        require(not any(meta[k] for k in ('returned_objects_or_ownership_modified', 'opaque_registry_items_dereferenced',
                    'private_entry_invoked_directly', 'system_modified')), 'metadata observer scope')
        pairs = correlate(trace, meta)
        require(len(pairs) + 1 == meta['calls'] == len(meta['events']), 'metadata association completeness')
        metadata_objects += len(pairs)
        decoded = d['public_decode']
        require(decoded['fixture_samples'] == 6 and decoded['format_create_status'] == 0, 'fixture accepted')
        codec = d['codec']
        if mode == 'cpu':
            require(dep['original_specification'] == dep['forwarded_specification']
                    == {'EnableHardwareAcceleratedVideoDecoder': False} and not dep['both_flags_applied'], 'CPU request unchanged')
            require(decoded['decode']['create_status'] == 0 and decoded['output_frames'] == 6
                    and decoded['different_bytes'] == decoded['missing_CPU_references'] == 0
                    and decoded['CPU_reference_bytes_compared'] == 691200
                    and decoded['decode']['decode_status'] == [0] * 6
                    and decoded['decode']['finish_status'] == decoded['decode']['wait_status'] == 0, 'software decode')
            for index, filename in enumerate(decoded['frame_files']):
                require(filename == 'vt-frame-%03d.nv12' % index, 'frame path')
                actual = (root / 'outputs' / filename).read_bytes()
                ref = (root / 'assets/fixtures' / codec / ('cpu-frame-%03d.nv12' % index)).read_bytes()
                require(len(actual) == 115200 and actual == ref, 'independent pixel bytes')
                CPU_frames += 1
                CPU_bytes += len(actual)
        else:
            both = expected_variant.endswith('-both')
            original = {'RequireHardwareAcceleratedVideoDecoder': True}
            forwarded = {**original, 'EnableHardwareAcceleratedVideoDecoder': True} if both else original
            require(dep['original_specification'] == original and dep['forwarded_specification'] == forwarded
                    and dep['both_flags_applied'] == both, 'strict hardware specification')
            require(dep['create_status'] == decoded['decode']['create_status'] == -12906
                    and decoded['output_frames'] == 0 and not decoded['frame_files']
                    and decoded['CPU_reference_bytes_compared'] == 0
                    and not list((root / 'outputs').glob('vt-frame-*.nv12')), 'retained hardware failure')
            hardware_failures += 1
        errors = [e for e in trace['events'] if e['index'] == 0]
        require([e['caller_offset'] for e in errors] == ([6290187, 20163] if changed else [20163])
                if mode == 'hardware' else not errors, 'actual error return sites')
        require(all(e['caller_image'] == profile['module'] and e['raw_integer_arguments'][2] & 0xffffffff
                    == (-12906 & 0xffffffff) for e in errors), 'actual error code registers')
        selected = [obj for raw, obj in pairs if raw['index'] == 3 and raw['caller_offset'] == 6289206]
        if changed:
            require(len(selected) == 1 and 'com.apple.videotoolbox.videodecoder.h264.gva' in selected[0]['description'], 'GVA reaches creation loop')
        elif mode == 'hardware':
            require(not selected, 'negative reaches creation loop unexpectedly')
        row.update(create_status=decoded['decode']['create_status'], frames=decoded['output_frames'],
            entry_calls=trace['calls'], error_return_offsets=[e['caller_offset'] for e in errors])
        if v2 and mode == 'hardware':
            require(trace['calls'] == (178 if changed else 87), 'balanced trace distinction')
            row['substitutions'] = dep['substitutions']
            counterfactual.append({'case': root.name, 'choice': choice, 'substitutions': dep['substitutions'],
                'entry_calls': trace['calls'], 'error_return_offsets': row['error_return_offsets'],
                'create_status': dep['create_status'], 'frames': 0,
                'executable_SHA256': run['executable_SHA256'],
                'executed_signed_SHA256': m['signed_binary_sha256'],
                'library_SHA256': run['dependency_libraries_SHA256']['both'],
                'assets_SHA256': run['assets_SHA256']})

    receipt('video-dependency-inspect-20261018', b1, 'inspect', 'inspect')
    for codec, kind, mode in [('H264', 'passive', 'cpu'), ('H264', 'observer', 'cpu'),
        ('H264', 'passive', 'hardware'), ('H264', 'observer', 'hardware'), ('H264', 'both', 'hardware'),
        ('MPEG2Video', 'observer', 'cpu'), ('MPEG2Video', 'observer', 'hardware')]:
        receipt('video-dependency-' + codec + '-' + kind + '-' + mode + '-20261018', b1, codec + '-' + kind, mode)
    receipt('video-dependency-v2-inspect-20261018', b2, 'inspect', 'inspect', v2=True)
    receipt('video-dependency-v2-H264-both-cpu-20261018', b2, 'H264-both', 'cpu', v2=True)
    for repeat in (1, 2, 3):
        for choice in ('native', 'wrong-key', 'present-key'):
            receipt('video-dependency-counterfactual-' + choice + '-r' + str(repeat) + '-20261018', b2,
                    'H264-both', 'hardware', choice, True)
    require(len(manifests) == 19 and CPU_frames == 24 and CPU_bytes == 2764800
            and hardware_failures == 13 and real_queries == 22 and query_controls == 38
            and scope_cases == 110, 'cohort totals')
    require(len({r['executable_SHA256'] for r in counterfactual}) == 1
            and len({r['executed_signed_SHA256'] for r in counterfactual}) == 1
            and len({r['library_SHA256'] for r in counterfactual}) == 1, 'same experimental signed binary/library')
    reference = counterfactual[0]['assets_SHA256']
    require(all({k: v for k, v in r['assets_SHA256'].items() if k != 'dependency-choice.json'}
                == {k: v for k, v in reference.items() if k != 'dependency-choice.json'} for r in counterfactual), 'only choice asset varies')
    for row in counterfactual:
        del row['assets_SHA256']
    patch = lab.parent / 'patches/video-dependency-v1-to-v2.patch'
    expected_patch = ''
    for published, frozen in [('video_dependency.mm', 'video_dependency.mm'), ('native_video_dependency.py', 'builder.py')]:
        rel = 'bridge/tools/' + published
        expected_patch += ''.join(difflib.unified_diff((b1 / frozen).read_text().splitlines(True),
            (b2 / frozen).read_text().splitlines(True), fromfile='a/' + rel, tofile='b/' + rel))
    require(patch.read_text() == expected_patch, 'source patch does not reconstruct the frozen versions')
    reconstruction = load(progress / 'source-and-scope-receipt.json')
    require(reconstruction['patch_SHA256'] == sha(patch) and reconstruction['status'] == 'PASS', 'independent reverse patch receipt')
    for published, frozen in [('video_dependency.mm', 'video_dependency.mm'), ('native_video_dependency.py', 'builder.py')]:
        require(reconstruction['reconstructed_v1_source_hashes'][published] == sha(b1 / frozen)
                == sha(progress / 'reconstructed-v1/bridge/tools' / published), 'reconstructed source hash')
    ordered = sorted(manifests, key=lambda m: m['started_at'])
    for before, after in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(before['completed_at']) <= datetime.datetime.fromisoformat(after['started_at']), 'overlapping native processes')
    balanced = [Path(m['original_executable']).parent.name for m in ordered if 'counterfactual-' in m['original_executable']]
    plan = load(progress / 'counterfactual-balanced-plan.json')['balanced_fresh_process_order']
    require(balanced == ['video-dependency-counterfactual-' + choice + '-r' + str(i + 1) + '-20261018'
                        for i, choices in enumerate(plan) for choice in choices], 'balanced observed ordering')
    cache_parts, regions = {}, []
    for name in ('video-dependency-static-20261016', 'video-dependency-next-static-20261018'):
        folder = results / name
        a = load(folder / 'analysis.json')
        require(a['status'] == 'STATIC_ONLY' and not a['vendor_program_executed']
                and not a['runtime_branch_proved'] and not a['system_modified'], 'static analysis scope')
        for source, digest in a['source_hashes'].items():
            require(sha(folder / source) == digest, 'static analyzer source')
        for index, row in enumerate(a['records']):
            capture = Path(row['capture'])
            require(sha(capture / 'metadata.json') == row['metadata_SHA256']
                    and sha(capture / 'function-region.private.bin') == row['region_SHA256']
                    and sha(folder / ('region-%02d' % index) / 'analysis.private.o') == row['container_SHA256']
                    and sha(folder / ('region-%02d' % index) / 'disassembly.private.txt') == row['disassembly_SHA256'], 'bounded private analysis')
            regions.append({k: row[k] for k in ('start_image_offset', 'region_bytes', 'region_SHA256')})
        for part in a['cache_parts_read']:
            previous = cache_parts.get(part['path'])
            require(previous is None or previous['SHA256'] == part['SHA256'], 'cache analysis drift')
            cache_parts[part['path']] = part
    for path, part in cache_parts.items():
        require(sha(path) == part['SHA256'], 'shared cache identity')
    start = load(progress / 'start.json')
    require(len(start['system_before']) == 83, 'protected inventory')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'protected system file changed')
    require(sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256'], 'OCLP changed')
    require(sha('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist') == start['policy_SHA256'], 'video policy changed')
    runtime = load(results / 'native-allocation-runtime-build-20261016-04/manifest.json')
    require(len(runtime['source_SHA256']) == 36, 'common runtime source inventory')
    for name, digest in runtime['source_SHA256'].items():
        require(sha(lab / name) == digest, 'common runtime source changed')
    return {'status': 'PASS', 'auditor_SHA256': sha(__file__), 'native_processes_terminal': 19, 'nonoverlapping': True,
        'public_query_controls': query_controls, 'pure_CPU_scope_contract_cases': scope_cases,
        'CPU_control_frames': CPU_frames, 'CPU_reference_bytes': CPU_bytes, 'CPU_different_bytes': 0,
        'hardware_required_failures': hardware_failures, 'hardware_create_status': -12906,
        'actual_native_property_queries': real_queries, 'actual_query_GPU_registry_ID': 4294968458,
        'real_CF_metadata_objects_correlated': metadata_objects,
        'counterfactual': {'repeats_per_choice': 3, 'same_executable_and_library': True,
            'same_executed_signed_executable': True,
            'only_choice_asset_varies': True, 'positive_scope_substitutions': 3, 'hardware_requirement_preserved': True,
            'GVA_reaches_creation_loop_return_offset': 6289206, 'new_error_return_offset': 6290187,
            'single_complete_root_cause_established': False, 'hardware_video_execution_proved': False, 'cases': counterfactual},
        'VideoToolbox_UUID': profile['UUID'], 'VideoToolbox_version': profile['version'], 'resident_code_pins': pins,
        'qualified_host_and_decoder_objects_reused': True, 'system_files_unchanged': 83,
        'original_source_v1_to_v2_patch_SHA256': sha(patch), 'v1_source_reconstruction_verified': True,
        'additional_video_policy_unchanged': True, 'OCLP_unchanged': True, 'common_runtime_sources_unchanged': 36,
        'static_regions': regions, 'cache_files': [{k: p[k] for k in ('name', 'UUID', 'SHA256')} for p in cache_parts.values()],
        'next_creator_offset': 2630814, 'next_creator_runtime_invocation_proved': False,
        'system_deployment': 'NOT RUN', 'performance_benchmark': 'NOT RUN', 'new_M1_execution': False,
        'Qwen_job_ids': [], 'hardware_video_execution_proved': False, 'full_objective_complete': False, 'processes': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise ValueError('Audit destination exists')
    result = audit(args.lab_root)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'native_processes_terminal', 'CPU_control_frames',
        'CPU_reference_bytes', 'hardware_required_failures', 'hardware_video_execution_proved')}))


if __name__ == '__main__':
    main()
