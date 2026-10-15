#!/usr/bin/env python3
"""Verify passive native-render framing and resource addresses; execute nothing."""
from pathlib import Path
import argparse, hashlib, json, struct
from decode_native_commands import decode
DRIVER = '2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054'
LIBRARY = '965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def u64(data, offset): return struct.unpack_from('<Q', data, offset)[0]
def verify(root, portable=False):
    d = json.loads((root / 'capture.json').read_text())
    inp = json.loads((root / 'inputs.json').read_text()); m = json.loads((root / 'execution/manifest.json').read_text())
    assert d['registry_id'] == 4294968458 and d['driver_SHA256'] == DRIVER
    assert sha(root / 'render_state_carrier.metallib') == inp['library_SHA256'] == d['library_SHA256'] == LIBRARY
    for name, h in inp['source_hashes'].items(): assert sha(root / name) == h
    assert not d['committed'] and not d['native_memory_modified'] and not d['GPU_user_submissions']
    assert m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    if not portable:
        assert sha(root / 'native_render_command_capture') == m['original_binary_sha256']
        assert sha(root / 'execution/native_render_command_capture') == m['signed_binary_sha256']
    v = next(v for v in d['encoder_layout']['ivars'] if v['name'] == 'm_renderer')
    q = next(v for v in d['queue_layout']['ivars'] if v['name'] == '_queue')
    assert d['encoder_layout']['class'] == 'NVMTLRenderCommandEncoder_KEPLER_A'
    assert d['encoder_layout']['instance_bytes'] == 128 and v['offset'] == 120 and q['offset'] == 680
    assert 'PushBuffer' in v['type'] and 'KeplerRenderCommandEncoder<41111, 0>' in v['type']
    evidence = []; raw_hashes = {}
    for i, r in enumerate(d['records']):
        assert i == r['step'] and r['range_comparable']
        before, after = r['before'], r['after']; assert before['push'] == after['push'] and before['end'] == after['end']
        assert before['queue'] == after['queue'] == q['address'] and before['push_field_offset'] == 32
        for suffix, c in [('before', before), ('after', after)]:
            p = root / 'outputs' / f'draw-{i}-{suffix}.context.bin'; a = p.read_bytes(); raw_hashes[p.name] = sha(p)
            assert u64(a, 16) == c['queue'] and u64(a, 32) == c['push']
            p = root / 'outputs' / f'draw-{i}-{suffix}.push.bin'; a = p.read_bytes(); raw_hashes[p.name] = sha(p)
            assert u64(a, 0) == c['current'] and u64(a, 136) == c['end']
        c = r['command_capture']; p = root / 'outputs' / Path(c['file']).name; a = p.read_bytes(); raw_hashes[p.name] = sha(p)
        assert sha(p) == c['SHA256'] and len(a) == c['bytes'] == after['current'] - before['current']
        packets = decode(a); assert sum(x['bytes'] for x in packets) == len(a) and all(x['subchannel'] == 0 for x in packets)
        if i < 3:
            assert len(a) == 24 and len(packets) == 1
        if i == 3:
            assert len(a) == 216 and len(packets) == 17
            for slot, packet in enumerate(packets[:-1]):
                assert packet['method_addresses'] == [hex(0xe04 + slot * 16), hex(0xe08 + slot * 16)]
                assert packet['values'] == [(63 << 16) | 1, (47 << 16) | 1]
        if i < 4:
            assert packets[-1]['method'] == '0x3830' and packets[-1]['values'] == [4, 3, 1, 0, 0]
        else:
            assert len(a) == 60 and len(packets) == 3
            assert packets[0]['method'] == '0x1644' and packets[0]['values'] == [0]
            begin = d['index_buffer_GPU_address'] + 64; end = begin + 63
            assert packets[1]['method'] == '0x17c8' and packets[1]['values'] == [begin >> 32, begin & 0xffffffff, end >> 32, end & 0xffffffff, 1]
            assert packets[-1]['method'] == '0x3840' and packets[-1]['values'] == [4, 3, 1 if i == 4 else 2, 0, 0, 0]
        evidence.append({'step': i, 'bytes': len(a), 'packets': len(packets), 'decoded': packets})
    return {'status': 'PASS_PASSIVE_CAPTURE', 'GPU_user_submissions': 0, 'native_memory_modified': False,
            'system_modified': False, 'render_ICB_implemented': False, 'raw_SHA256': raw_hashes,
            'records': evidence, 'portable_raw_verification_only': portable,
            'host_executable_SHA256_rechecked': not portable,
            'scope': 'Own-process native draw/index-buffer/scissor framing. MME slots6/8 are driver-defined; Mesa slot names do not establish their meaning.'}
if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--input', type=Path, required=True); p.add_argument('--portable', action='store_true'); a = p.parse_args()
    root = a.input.resolve(); r = verify(root, a.portable)
    (root / 'independent-verification.json').write_text(json.dumps(r, indent=2) + '\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('raw_SHA256','records')}, indent=2))
