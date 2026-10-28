#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read the GTX PCI registry identity and RM board property, without opening it."""
import argparse
import json
import plistlib
import subprocess
from pathlib import Path

def inspect_tree(tree):
    matches = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            vendor, device = value.get('vendor-id'), value.get('device-id')
            if (isinstance(vendor, bytes) and len(vendor) == 4 and
                isinstance(device, bytes) and len(device) == 4 and
                int.from_bytes(vendor, 'little') == 0x10de and
                int.from_bytes(device, 'little') == 0x1198):
                matches.append(value)
            for item in value.values():
                walk(item)
    walk(tree)
    if len(matches) != 1:
        raise ValueError('expected exactly one matching NVIDIA PCI device')
    row = matches[0]
    board, rid = row.get('rm_board_number'), row.get('IORegistryEntryID')
    if not isinstance(board, bytes) or len(board) != 4:
        raise ValueError('rm_board_number must be four bytes')
    if type(rid) is not int or rid <= 0:
        raise ValueError('PCI registry identity missing')
    return {'status': 'PASS_REGISTRY_OBSERVATION', 'pci_registry_id': rid,
            'pci_name': row.get('IORegistryEntryName'), 'vendor_id': '0x10de',
            'device_id': '0x1198', 'board_value_u32_le': int.from_bytes(board, 'little'),
            'board_property_length': len(board), 'matching_devices': 1,
            'scope': 'Registry property only; no loaded-driver path, RM handle or device allocation is established.',
            'IOServiceOpen_calls': 0, 'private_RM_calls': 0, 'GPU_dispatches': 0}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    if not args.out.parent.is_dir() or args.out.exists():
        raise ValueError('fresh output required')
    result = subprocess.run(['ioreg', '-a', '-r', '-l', '-c', 'IOPCIDevice', '-w', '0'],
                            capture_output=True, check=True, timeout=30)
    if len(result.stdout) > 32 * 1024 * 1024:
        raise ValueError('registry response exceeds bound')
    observation = inspect_tree(plistlib.loads(result.stdout))
    with args.out.open('x') as f:
        json.dump(observation, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(observation, sort_keys=True))

if __name__ == '__main__':
    main()
