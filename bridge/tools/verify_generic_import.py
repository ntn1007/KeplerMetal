#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Portable raw-output oracles for the bounded generic import cohort."""
from pathlib import Path
import math
import struct
from verify_local_memory import verify_device_identity


def imports(proof, stages):
    assert proof['contract_verified'] and proof['constructor_restored']
    events = [e for e in proof['events'] if e.get('code_replaced')]
    assert {e['stage'] for e in events} == set(stages)
    for e in events:
        assert e['imported_code_identical']
        if e['stage'] != 5: assert e['original_graphics_header_preserved']
    return len(events)


def floats(path):
    raw = Path(path).read_bytes()
    assert len(raw) % 4 == 0
    values = struct.unpack('<' + 'f' * (len(raw) // 4), raw)
    assert all(math.isfinite(v) for v in values)
    return values


def vertex_reference(draw, mode, interpolation):
    """CPU perspective interpolation from four source vertices, no GPU inputs."""
    assert mode in ['native', 'vertex', 'fragment', 'both']
    assert interpolation in ['smooth', 'linear', 'flat']
    instanced = draw in ['instanced', 'base-instance', 'indirect', 'indirect-indexed', 'indirect-control']
    base = 3 if draw in ['base-instance', 'indirect', 'indirect-indexed', 'indirect-control'] else 0
    xy = [(-1, -1), (0 if instanced else 1, -1), (-1, 1), (0 if instanced else 1, 1)]
    colors = [(.25,.125,.75,1),(.75,.25,.5,1),(.125,.75,.25,1),(.5,.5,.875,1)]
    ws = [.5,1,2,1]; triangles = []
    for instance in range(0 if draw == 'indirect-control' else 2 if instanced else 1):
        vertices = []
        for i in [0,1,2,2,1,3]:
            color = list(colors[i])
            if mode in ['vertex','both']: color = [v * .5 + (.5 if c == 3 else .125) for c,v in enumerate(color)]
            color[2] += (base + instance) * (1/32 if mode in ['vertex','both'] else 1/64) + (base + instance)/64
            vertices.append(((xy[i][0] + instance + 1)*32, (1 - xy[i][1])*24, ws[i], color))
        triangles.extend([vertices[:3],vertices[3:]])
    output = []
    def cross(ax, ay, bx, by): return ax*by-ay*bx
    for y in range(48):
        for x in range(64):
            expected = [0.0]*4
            for a,b,c in triangles:
                area = cross(b[0]-a[0],b[1]-a[1],c[0]-a[0],c[1]-a[1])
                l1 = cross(x+.5-a[0],y+.5-a[1],c[0]-a[0],c[1]-a[1])/area
                l2 = cross(b[0]-a[0],b[1]-a[1],x+.5-a[0],y+.5-a[1])/area
                weights = [1-l1-l2,l1,l2]
                if min(weights) < -1e-10: continue
                if interpolation == 'flat': expected = list(a[3])
                else:
                    if interpolation == 'smooth':
                        weights = [w/v[2] for w,v in zip(weights,[a,b,c])]; total = sum(weights)
                        weights = [w/total for w in weights]
                    expected = [sum(w*v[3][i] for w,v in zip(weights,[a,b,c])) for i in range(4)]
                if mode in ['fragment','both']: expected = [v*.75+bias for v,bias in zip(expected,[.0625,.125,.1875,.25])]
            output.extend(expected)
    return output


def verify_vertex(result, prefix):
    verify_device_identity(result); assert result['command_status'] == 4
    assert result['mismatched_channels'] == result['argument_mismatches'] == result['changed_argument_guards'] == 0
    mode, draw = result['mode'], result['draw']
    stages = ({0} if mode == 'vertex' else {4} if mode == 'fragment' else {0,4} if mode == 'both' else set())
    count = imports(result['render_import'], stages) if stages else 0
    actual = floats(str(prefix) + '.image.bin')
    expected = vertex_reference(draw,mode,result['interpolation'])
    assert len(actual) == len(expected) == 64*48*4
    error = max(abs(a-b) for a,b in zip(actual,expected)); assert error <= 2e-6
    arguments = 0
    if draw in ['indirect','indirect-indexed','indirect-control']:
        values = struct.unpack('<8I',Path(str(prefix)+'.arguments.bin').read_bytes())
        words = 5 if draw == 'indirect-indexed' else 4
        expected_words = ([6,2,3,2,3] if words == 5 else [6,2,0,3])
        if draw == 'indirect-control': expected_words = [0]*words
        assert list(values[:words]) == expected_words and list(values[words:]) == [0xc0fe24b1]*(8-words)
        assert result['argument_buffer_private'] and not result['argument_CPU_read_before_submit']
        if draw != 'indirect-control': count += imports(result['compute_import'],{5})
        arguments = words
    return dict(status='PASS',float32_channels=len(actual),argument_words=arguments,imports=count,max_error=error)


def verify_tess(result, prefix):
    verify_device_identity(result); assert result['command_status'] == 4
    assert result['mismatches'] == result['guard_mismatches'] == result['tail_mismatches'] == 0
    raw = [Path(str(prefix)+f'.buffer-{i}.bin').read_bytes() for i in range(3)]
    sizes = [4,32768*16,32768*16]
    for b,size in zip(raw,sizes):
        assert len(b) == size+128 and b[:64] == b[-64:] == bytes([0xa5])*64
    n = struct.unpack_from('<I',raw[0],64)[0]
    assert n == result['invocations'] and n <= 32768
    assert (n == 0) if result['factor'] == 0 else (n >= 3)
    for b in raw[1:]: assert b[64+n*16:-64] == bytes([0xa5])*(32768-n)*16
    coords, values = floats(str(prefix)+'.coords.bin'), floats(str(prefix)+'.values.bin')
    assert len(coords) == len(values) == n*4
    assert raw[1][64:64+n*16] == Path(str(prefix)+'.coords.bin').read_bytes()
    assert raw[2][64:64+n*16] == Path(str(prefix)+'.values.bin').read_bytes()
    error = 0.0
    for i in range(n):
        c = coords[i*4:i*4+4]; assert all(0<=v<=1 for v in c) and c[3] == 1 and abs(sum(c[:3])-1)<=2e-7
        expected = [v*v for v in c[:3]]
        if result['NAK_imported']: expected = [v*.5+.125 for v in expected]
        expected.append(1)
        error = max(error,max(abs(a-b) for a,b in zip(values[i*4:i*4+4],expected)))
    assert error <= 1e-7
    count = imports(result['import'],{2}) if result['NAK_imported'] else 0
    return dict(status='PASS',invocations=n,float32_channels=n*4,guard_bytes=384,
        untouched_tail_bytes=(32768-n)*32,imports=count,max_error=error)


def verify_contract(result):
    verify_device_identity(result)
    assert result['status'] == 'PASS' and result['GPU_dispatches'] == 0
    assert result['outer_pipeline_created'] and result['constructor_restored_after_join']
    assert {r['API'] for r in result['nested_imports']} == {'generic_compute','generic_graphics','certified_CAS','invalid_CAS'}
    assert len(result['nested_imports']) == 4 and all(r['refused'] and 'Nested' in r['error'] for r in result['nested_imports'])
    count = imports(result['outer_import'],{5})
    assert len(result['concurrent_imports']) == 3 and {r['kind'] for r in result['concurrent_imports']} == {0,1,2}
    for r in result['concurrent_imports']:
        p = r['proof']; assert p['constructor_restored']
        if r['kind'] == 0:
            assert r['expected_cached_refusal'] and not r['pipeline_created'] and not p['contract_verified']
            assert p['target_imports'] == p['verified_imports'] == 0 and not p['rejected_import']
            assert 'Decoded program contract did not match' in r['error']
        else:
            assert r['pipeline_created'] and not r['expected_cached_refusal']
            count += imports(p['native_import'] if r['kind'] == 2 else p,{5} if r['kind'] == 2 else {0,4})
    return dict(status='PASS',imports=count,nested_refusals=4,concurrent_callers=3,cached_pipeline_refusals=1,GPU_dispatches=0)
