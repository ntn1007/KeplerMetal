#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a bounded AppleGVA string call and retained driver plist profiles."""
import argparse
import hashlib
import json
import plistlib
import re
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = 'a877c0ef81fbbb4d42bee6c1de063fff47d610a5397ffc6ce7617f28269bfe73'
PAYLOAD = 'd7d5b7c6957f59a1287ba50987c1968f1a9cb12031c09b5bff05d3743f315528'
HIGH_INFO = '2b666df85091a02c6610cc517523e923b6a7e434cc8f974caf9d0e981a3b392e'
CURRENT_INFO = '994ef3f131f22c5b528e5a2b05b02c80567397026e8e4a83eb88b1715f52959b'
REGION = 'f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19'
MAP = '2d9c4ed04bcdbdd4049bb7ed88f0a545d3f42b1b478ab320e43fc8feb6a39ffd'
PAYLOAD_MEMBER = '1.8-103-387.10.10.10.40.140-NVWebDrivers.pkg/Payload'
KEXT_NAMES = ('GeForceTeslaWeb', 'GeForceWeb', 'NVDAGF100HalWeb', 'NVDAGK100HalWeb',
              'NVDAGM100HalWeb', 'NVDAGP100HalWeb', 'NVDANV50HalTeslaWeb',
              'NVDAResmanTeslaWeb', 'NVDAResmanWeb', 'NVDAStartupWeb')


def need(ok, why):
    if not ok:
        raise ValueError(why)


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def command(argv, allowed=(0,), timeout=120):
    result = subprocess.run([str(x) for x in argv], capture_output=True, timeout=timeout)
    need(result.returncode in allowed, str(argv[0]) + ' returned ' + str(result.returncode))
    return result


def key_paths(value, key, path=()):
    result = []
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key:
                result.append(path + (name,))
            result.extend(key_paths(child, key, path + (str(name),)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            result.extend(key_paths(child, key, path + (str(index),)))
    return result


def static_contract(data):
    need(hashlib.sha256(data).hexdigest() == REGION, 'AppleGVA region differs')
    start = 148746
    # Null test, conditional flag store, and CFStringGetCString arguments.
    expected = bytes.fromhex('e852110a004885c074294989c741c6866304000001498d7608ba200000004889c7b900060000e818100a004c89ffe8e60f0a00')
    need(data[150807-start:150858-start] == expected, 'property conversion sequence differs')
    return {'property_call_offset': 150807, 'null_target_offset': 150858,
            'flag_write_before_conversion_offset': 150821, 'string_call_offset': 150845,
            'buffer_offset_in_node': 8, 'buffer_bytes': 32, 'encoding_constant': 1536,
            'conversion_return_checked_in_captured_sequence': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('package', 'high-bundle', 'current-plist', 'property-region', 'property-map', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    need(sha_file(a.package) == PACKAGE and sha_file(a.property_region) == REGION and
         sha_file(a.property_map) == MAP, 'pinned input differs')
    contract = static_contract(a.property_region.read_bytes())
    mapping = json.loads(a.property_map.read_text())
    rows = {x['caller_offset']: x for x in mapping['rows']}
    need(mapping['status'] == 'STATIC_ONLY' and not mapping['runtime_target_proved'] and
         '_IORegistryEntryCreateCFProperty' in rows[150807]['exact_defined_symbols'] and
         '_CFStringGetCString' in rows[150845]['exact_defined_symbols'], 'static stub map differs')
    high_info = a.high_bundle / 'Contents/Info.plist'
    need(sha_file(high_info) == HIGH_INFO and sha_file(a.current_plist) == CURRENT_INFO, 'Apple plist differs')
    command(['codesign', '--verify', '--strict', a.high_bundle])
    apple = []
    for label, path, version in [('high_sierra', high_info, '10.3.2'), ('current', a.current_plist, '16.0.0')]:
        data = path.read_bytes()
        info = plistlib.loads(data)
        need(info['CFBundleVersion'] == version and not key_paths(info, 'IOGVACodec'), label + ' profile differs')
        ge = info['IOKitPersonalities']['GeForce']
        need(ge['IODVDBundleName'] == 'GeForceVADriver' and ge['IOVABundleName'] == 'GeForceVADriver',
             label + ' bundle name differs')
        apple.append({'profile': label, 'bundle_version': version, 'plist_sha256': hashlib.sha256(data).hexdigest(),
                      'codec_key_in_plist': False, 'video_bundle_name': 'GeForceVADriver'})
    positive = []
    for family, path, want in [
        ('Intel_ICL', '/System/Library/Extensions/AppleIntelICLGraphics.kext/Contents/Info.plist', 'Gen11'),
        ('AMD_Navi', '/System/Library/Extensions/AMDRadeonX6000.kext/Contents/Info.plist', 'AMDVCN2')]:
        data = Path(path).read_bytes()
        info = plistlib.loads(data)
        values = [v['IOGVACodec'] for v in info.get('IOKitPersonalities', {}).values() if 'IOGVACodec' in v]
        need(values and all(type(x) is str and x == want for x in values), family + ' positive control differs')
        positive.append({'family': family, 'plist_sha256': hashlib.sha256(data).hexdigest(),
                         'string_value': want, 'personality_count': len(values), 'active_GPU_proved': False})
    signature = command(['pkgutil', '--check-signature', a.package], allowed=(0, 1), timeout=45)
    signature_text = (signature.stdout + signature.stderr).decode('utf-8', 'replace')
    expired = 'signed by a certificate that has since expired' in signature_text
    need(expired and signature.returncode == 1, 'package trust result changed; requalify')
    archive_rows = []
    with tempfile.TemporaryDirectory(prefix='codec-contract-', dir=a.out.parent) as temp:
        command(['xar', '-xf', a.package, '-C', temp, PAYLOAD_MEMBER], timeout=120)
        payload = Path(temp) / PAYLOAD_MEMBER
        need(sha_file(payload) == PAYLOAD, 'package payload differs')
        listing = command(['bsdtar', '-tf', payload]).stdout.decode('utf-8').splitlines()
        names = [x for x in listing if re.fullmatch(r'\./Library/Extensions/[^/]+\.kext/Contents/Info\.plist', x)]
        expected_names = {'./Library/Extensions/' + n + '.kext/Contents/Info.plist' for n in KEXT_NAMES}
        need(len(names) == len(expected_names) and set(names) == expected_names, 'kext member inventory differs')
        for member in sorted(names):
            data = command(['bsdtar', '-xOf', payload, member]).stdout
            need(len(data) <= 4 * 1024 * 1024, 'plist too large')
            info = plistlib.loads(data)
            paths = key_paths(info, 'IOGVACodec')
            need(not paths, 'unexpected IOGVACodec key in archived plist')
            archive_rows.append({'member': member, 'sha256': hashlib.sha256(data).hexdigest(),
                                 'bundle_version': info.get('CFBundleVersion'), 'codec_key_in_plist': False})
        host = Path(temp) / 'cf-control'
        command(['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                 HERE / 'cf_ascii_control.cpp', '-framework', 'CoreFoundation', '-o', host])
        control = json.loads(command([host], timeout=15).stdout)
        need(control['status'] == 'PASS' and control['guards_intact'] and not control['GPU_execution'] and
             not control['vendor_execution'], 'CoreFoundation control differs')
        host_sha = sha_file(host)
    receipt = {'status': 'PASS_BOUNDED_CODEC_CONTRACT_AUDIT', 'static_contract': contract,
               'region_sha256': REGION, 'static_stub_map_sha256': MAP,
               'call_contract_scope': 'Pinned AppleGVA path, not proof of a valid NVIDIA value or live non-null call.',
               'current_and_high_sierra_apple_plists': apple, 'other_vendor_plist_controls': positive,
               'web_driver_package_sha256': PACKAGE, 'web_driver_payload_sha256': PAYLOAD,
               'package_signature_current_status': 'expired_certificate',
               'package_current_trust_verified': False, 'web_driver_plists': archive_rows,
               'web_driver_executables_scanned': False, 'property_may_be_set_dynamically': True,
               'nvidia_codec_value_identified': False, 'gpu_support_proved': False,
               'cf_control': control, 'cf_control_source_sha256': sha_file(HERE / 'cf_ascii_control.cpp'),
               'cf_control_binary_sha256': host_sha, 'auditor_source_sha256': sha_file(Path(__file__)),
               'GPU_execution': False, 'vendor_execution': False, 'system_modified': False}
    with a.out.open('x') as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write('\n')
    print(json.dumps({'status': receipt['status'], 'nvidia_plists': len(archive_rows),
                      'nvidia_codec_value_identified': False, 'GPU_execution': False}))


if __name__ == '__main__':
    main()
