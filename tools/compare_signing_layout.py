#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare all pre-signature bytes while validating signature-size fields.

This is deliberately separate from the stricter CMS-only comparator. It reports
file evidence, never authenticates a signature, and never authorizes a driver.
"""
import argparse
import json
from pathlib import Path
import struct
from compare_driver_signatures import sha, signature


def layout(data):
    parsed = signature(data)
    ncmds, sizeofcmds = struct.unpack_from('<II', data, 16)
    offset, end = 32, 32+sizeofcmds
    segments, sig_commands = [], []
    for _ in range(ncmds):
        cmd, size = struct.unpack_from('<II',data,offset)
        if cmd == 0x19:
            if size < 72:
                raise ValueError('Truncated segment command')
            name = data[offset+8:offset+24].split(b'\0',1)[0]
            if name == b'__LINKEDIT':
                fileoff, filesize = struct.unpack_from('<QQ',data,offset+40)
                segments.append({'command_offset':offset,'fileoff':fileoff,'filesize':filesize,
                                 'filesize_field':offset+48})
        elif cmd == 0x1d:
            if size != 16:
                raise ValueError('Invalid signature command')
            sig_commands.append({'command_offset':offset,'size_field':offset+12})
        offset += size
    if offset != end or len(segments) != 1 or len(sig_commands) != 1:
        raise ValueError('Expected unique LINKEDIT and signature commands')
    segment, command = segments[0], sig_commands[0]
    start, size = parsed['offset'],parsed['size']
    if (start+size != len(data) or segment['fileoff'] > start or
            segment['fileoff']+segment['filesize'] != len(data)):
        raise ValueError('Signature must terminate the file and LINKEDIT')
    if segment['filesize_field']+8 > end or command['size_field']+4 > end:
        raise ValueError('Size fields must lie in the load commands')
    return {'signature':parsed,'segment':segment,'command':command,'length':len(data)}


def compare(left, right):
    a,b = layout(left),layout(right)
    if (a['signature']['offset'] != b['signature']['offset'] or
        a['segment']['fileoff'] != b['segment']['fileoff'] or
        a['segment']['filesize_field'] != b['segment']['filesize_field'] or
        a['command']['size_field'] != b['command']['size_field']):
        return {'classification':'LAYOUT_NOT_COMPARABLE','left_SHA256':sha(left),'right_SHA256':sha(right),
                'runtime_compatibility_proved':False,'signature_authenticity_checked':False}
    start = a['signature']['offset']
    aa,bb = bytearray(left[:start]),bytearray(right[:start])
    fields = [(a['segment']['filesize_field'],8,'LINKEDIT.filesize'),
              (a['command']['size_field'],4,'LC_CODE_SIGNATURE.datasize')]
    differences = sum(x != y for x,y in zip(aa,bb))
    field_changes = []
    for offset,size,name in fields:
        field_changes.append({'name':name,'file_offset':offset,'bytes':size,
                              'different':aa[offset:offset+size] != bb[offset:offset+size]})
        aa[offset:offset+size] = b'\0'*size
        bb[offset:offset+size] = b'\0'*size
    same = aa == bb
    return {'classification':'SAME_PRE_SIGNATURE_EXCEPT_VALIDATED_SIZE_FIELDS' if same else 'OTHER_PRE_SIGNATURE_DIFFERENCES',
            'left_SHA256':sha(left),'right_SHA256':sha(right),'signature_offset':start,
            'left_signature_bytes':a['signature']['size'],'right_signature_bytes':b['signature']['size'],
            'raw_pre_signature_different_bytes':differences,'validated_size_fields':field_changes,
            'normalized_pre_signature_SHA256_left':sha(aa),'normalized_pre_signature_SHA256_right':sha(bb),
            'normalized_pre_signature_equal':same,'tail_outside_signature':False,
            'signature_authenticity_checked':False,'runtime_compatibility_proved':False,'GPU_execution':False,
            'limits':['Compared these two local files only; no historic third file inferred.',
                      'Normalized only the two validated size fields, not arbitrary byte differences.',
                      'Loaded kernel memory and cryptographic signatures were not authenticated.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference',type=Path);p.add_argument('candidate',type=Path)
    a=p.parse_args();print(json.dumps(compare(a.reference.read_bytes(),a.candidate.read_bytes()),indent=2))

if __name__ == '__main__': main()
