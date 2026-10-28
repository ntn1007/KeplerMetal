#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline, conservative checks for one historical NVIDIA registration path.

This is not an ABI encoder and must not be used to call the provider.
"""
import argparse
import hashlib
import json
from pathlib import Path

PROVIDER_SHA = 'bf2110a8a74786fe06da672e35f05a0dbd554aa651a83bacf02753c5899ef567'
REGIONS = {
    'factory': (0x1f3dc, 0x1f617, '1e1a7d142798e87f6a263940d321f002859dd5c3114d844205d5abdd78dad89d'),
    'registration': (0x2afa0, 0x2b09f, '068e37ce92afb5a584180995d723a67ab118fc3911f32dd70751e4d211725027'),
    'selection': (0x2ba56, 0x2bac9, 'a08b1d1c3ff92c0f2d493d6dd4ca11ebf850241a2c29698e6bc77a9f2cd7b552'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_provider(data):
    if digest(data) != PROVIDER_SHA:
        raise ValueError('provider identity differs')
    if data[:4] != b'\xcf\xfa\xed\xfe':
        raise ValueError('not a 64-bit little-endian Mach-O')
    for name, (start, end, expected) in REGIONS.items():
        if digest(data[start:end]) != expected:
            raise ValueError('region differs: ' + name)
    return {name: {'file_offset': start, 'length': end - start, 'SHA256': expected}
            for name, (start, end, expected) in REGIONS.items()}


def assess(index, mask, words):
    """Model only necessary local registration/selection checks; no ABI construction."""
    valid_u32 = lambda x: type(x) is int and 0 <= x <= 0xffffffff
    if not valid_u32(index) or not valid_u32(mask):
        raise ValueError('index and mask must be uint32')
    if type(words) not in (list, tuple) or any(not valid_u32(w) for w in words):
        raise ValueError('words must be a sequence of uint32')
    count = mask.bit_length()
    if not mask:
        return {'eligible': False, 'reason': 'zero-mask', 'required_words': 0}
    if len(words) < count:
        return {'eligible': False, 'reason': 'short-table', 'required_words': count}
    if index >= count:
        return {'eligible': False, 'reason': 'index-out-of-range', 'required_words': count}
    if not mask & (1 << index):
        return {'eligible': False, 'reason': 'index-disabled', 'required_words': count}
    if words[index] == 0:
        return {'eligible': False, 'reason': 'zero-entry', 'required_words': count}
    return {'eligible': True, 'reason': 'local-conditions-only', 'required_words': count}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--provider', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():
        raise ValueError('fresh output required')
    regions = verify_provider(a.provider.read_bytes())
    cases = [
        (0, 1, [1]), (0, 0, []), (31, 0x80000000, [1]),
        (0, 0x80000001, [1]), (1, 5, [1, 1, 1]),
        (2, 5, [1, 1, 0]), (32, 0x80000000, [1] * 32),
        (31, 0x80000000, [0] * 31 + [1]),
    ]
    result = {'status': 'PASS', 'provider_SHA256': PROVIDER_SHA, 'regions': regions,
              'evidence_ids': ['ev_122fc54c910d30b1fd59c051b77166f63d26bb2410be662865dcb02643d522bc',
                               'ev_740fd0cfab7948a61300a27da572e9cda25cb1b28442af931601b1b8e92a422d'],
              'cases': [{'index': i, 'mask': mask, 'provided_words': len(words), **assess(i, mask, words)}
                        for i, mask, words in cases],
              'runtime_provider_called': False, 'GPU_video_executed': False,
              'meaning_of_words_proved': False, 'sufficient_for_provider_success': False,
              'scope': 'Static pinned binary and conservative offline model; no ABI or runtime compatibility established.'}
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
