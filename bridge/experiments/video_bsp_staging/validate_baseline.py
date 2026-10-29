#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare a bounded baseline header extractor with an independent FFmpeg trace."""
import argparse
import base64
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURE_SHA = '12858642f02b0e1d98ddf409dd729a879b6a7a5d3434c860882532ca4f6b40af'
EXPECTED = {'fixture.json':'fdd6b495c5710c210dee34c5ef4e2c5894d6be3deeeeed2aae2bf43d4073152c',
 'frame-000.avcc':'8b0f93f2bf081d7e413bcd75f35cba8361be21dbf4afbd92c130e4c80d34048c',
 'frame-001.avcc':'5c23f0e206472abaf7e051a016c99184b4fb8c6a8cf8c71b0dc7cc2f1b99ae03',
 'frame-002.avcc':'fcdf3656e7624c8fc0b5d063724df2cba390c2b183a932ad0f9adf843bacda9d',
 'frame-003.avcc':'6cf9f20f947526056e8d3378f6c0623068e8df3fcd2a721022fa04262a1ba9f1',
 'frame-004.avcc':'e2a9ff1fbfae5284a01d3ad11f3026fa2dda1f756245849d59cd17edf75ac942',
 'frame-005.avcc':'881c77a204f55337cbb39eca2f46af1ca301c67b5774d23787e163c7d7a9411a'}


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(condition, message):
    if not condition: raise ValueError(message)
def fields(text):
    pairs = re.findall(r'\]\s+\d+\s+([A-Za-z0-9_]+)\s+[01]+\s+=\s+(-?\d+)', text)
    return {name: int(value) for name, value in pairs}
def command(label, args, out):
    result = subprocess.run(list(map(str, args)), capture_output=True, timeout=120)
    (out / (label + '.stdout')).write_bytes(result.stdout)
    (out / (label + '.stderr')).write_bytes(result.stderr)
    need(result.returncode == 0, label + ' failed; inspect stderr')
    return result.stdout


def annex_sample(data):
    output = bytearray(); pos = 0
    while pos < len(data):
        need(pos + 4 <= len(data), 'AVCC length truncated')
        n = int.from_bytes(data[pos:pos+4], 'big'); pos += 4
        need(n > 0 and pos + n <= len(data), 'AVCC NAL bounds')
        output += b'\0\0\0\1' + data[pos:pos+n]; pos += n
    return bytes(output)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('fixture', 'reference', 'out'): p.add_argument('--' + n, type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    need({x.name:sha(x) for x in a.fixture.iterdir() if x.is_file()} == EXPECTED, 'fixture differs')
    receipt = json.loads((a.reference / 'receipt.json').read_text())
    need(receipt['status'] == 'PASS_FFMPEG_TRACE_CAPTURE' and receipt['architecture'] == 'arm64' and
         receipt['fixture_sha256_before_after'] == FIXTURE_SHA and receipt['exit_code'] == 0 and
         receipt['before_sha256'] == sha(a.reference / 'before.txt') == sha(a.reference / 'after.txt') and
         receipt['trace_sha256'] == sha(a.reference / 'trace.txt') and
         receipt['stdout_sha256'] == sha(a.reference / 'stdout.txt') and
         receipt['capture_source_sha256'] == sha(HERE / 'capture_trace.py'), 'reference capture differs')
    identity = (a.reference / 'before.txt').read_text().splitlines()
    need(len(identity) == 4 and identity[0] == receipt['architecture'] and identity[1] == receipt['ffmpeg_version'] and
         len(identity[2].split(None, 1)) == 2 and identity[2].split(None, 1)[0] == receipt['binary_sha256_before_after'] and
         len(identity[3].split(None, 1)) == 2 and identity[3].split(None, 1)[0] == FIXTURE_SHA,
         'reference identity record differs')
    trace = (a.reference / 'trace.txt').read_text()
    need(trace.count('Sequence Parameter Set') >= 1 and trace.count('Picture Parameter Set') >= 1, 'parameter trace missing')
    sp = fields(trace.split('Sequence Parameter Set',1)[1].split('Picture Parameter Set',1)[0])
    pp = fields(trace.split('Picture Parameter Set',1)[1].split('Stream mapping:',1)[0])
    packets = re.split(r'\[trace_headers @ [^\]]+\] Packet:', trace)[1:]
    need(len(packets) == 6 and sp['profile_idc'] == 66 and sp['pic_order_cnt_type'] == 0 and
         sp['frame_cropping_flag'] == 0 and sp['frame_mbs_only_flag'] == 1 and
         pp['num_slice_groups_minus1'] == 0 and pp['num_ref_idx_l1_default_active_minus1'] == 0,
         'unsupported reference profile')
    meta = json.loads((a.fixture / 'fixture.json').read_text())
    need(meta['NAL_length_bytes'] == 4 and len(meta['H264_parameter_sets_base64']) == 2 and len(meta['frames']) == 6,
         'fixture metadata differs')
    params = [base64.b64decode(x, validate=True) for x in meta['H264_parameter_sets_base64']]
    annex = b''.join(b'\0\0\0\1' + x for x in params)
    for i in range(6): annex += annex_sample((a.fixture / ('frame-%03d.avcc' % i)).read_bytes())
    need(hashlib.sha256(annex).hexdigest() == FIXTURE_SHA, 'fixture/reference Annex-B mismatch')
    a.out.mkdir()
    for i, data in enumerate(params): (a.out / ('param-%d.bin' % i)).write_bytes(data)
    common = ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-O1', '-g', '-fsanitize=undefined']
    base = ['xcrun','clang++', *common, HERE / 'H264Stream.cpp', HERE / 'H264Baseline.cpp', HERE / 'VideoLayout.cpp']
    command('build-test', [*base, HERE / 'test_baseline.cpp', '-o', a.out / 'test'], a.out)
    command('test', [a.out / 'test'], a.out)
    command('build-tool', [*base, HERE / 'baseline_tool.cpp', '-o', a.out / 'baseline'], a.out)
    rows = []
    for i, packet in enumerate(packets):
        sample = a.fixture / ('frame-%03d.avcc' % i)
        slices = [fields(x) for x in packet.split('Slice Header')[1:]]
        need(len(slices) == 2 and all(s['pic_parameter_set_id'] == pp['pic_parameter_set_id'] for s in slices), 'slice trace differs')
        output = a.out / ('frame-%d.bin' % i)
        got = json.loads(command('frame-%d' % i, [a.out / 'baseline', a.out / 'param-0.bin', a.out / 'param-1.bin', sample, output], a.out))
        first = slices[0]
        need(all(s['slice_type'] == first['slice_type'] and s['frame_num'] == first['frame_num'] and
                 s['pic_order_cnt_lsb'] == first['pic_order_cnt_lsb'] for s in slices), 'inconsistent FFmpeg slice trace')
        l0 = 0 if first['slice_type'] == 2 else pp['num_ref_idx_l0_default_active_minus1']
        if first['slice_type'] == 0:
            need(all(s['num_ref_idx_active_override_flag'] == 0 for s in slices), 'reference override not covered')
        width = (sp['pic_width_in_mbs_minus1']+1)*16
        height = (sp['pic_height_in_map_units_minus1']+1)*16
        max_refs = sp['max_num_ref_frames']
        mbs_w, half_w, half_h, aligned_h = (width+15)//16, (width+31)//32, (height+31)//32, ((height+63)//64)*64
        reference_stride = mbs_w*16*(half_h*32 + aligned_h//2)
        temporary_stride = 16*half_w*aligned_h*3//2
        reference_bytes = reference_stride*(max_refs+2) + temporary_stride*(max_refs+1)
        intermediate = ((width*height*2 + (4<<20)-1)//(4<<20))*(4<<20)
        expected = {'width':width, 'height':height,
            'slice_count':len(slices), 'frame_num':first['frame_num'], 'poc_lsb':first['pic_order_cnt_lsb'],
            'slice_type':first['slice_type'], 'pps_id':first['pic_parameter_set_id'],
            'frame_log':sp['log2_max_frame_num_minus4'], 'poc_log':sp['log2_max_pic_order_cnt_lsb_minus4'],
            'frame_mbs_only':sp['frame_mbs_only_flag'], 'direct_8x8':sp['direct_8x8_inference_flag'],
            'entropy':pp['entropy_coding_mode_flag'], 'bottom_poc':pp['bottom_field_pic_order_in_frame_present_flag'],
            'l0':l0, 'l1':0, 'weighted':pp['weighted_pred_flag'], 'bipred':pp['weighted_bipred_idc'],
            'qp':pp['pic_init_qp_minus26'], 'deblock':pp['deblocking_filter_control_present_flag'],
            'redundant':pp['redundant_pic_cnt_present_flag'], 'first_macroblocks':[s['first_mb_in_slice'] for s in slices],
            'max_references':max_refs, 'reference_stride':reference_stride, 'reference_bytes':reference_bytes,
            'temporary_stride':temporary_stride, 'intermediate_bytes':intermediate,
            'initial_bytes':reference_bytes+2*intermediate+2*(1<<20),
            'flags':(len(slices) << 4) | 3 | (1 << 17)}
        need(got == expected, 'header fields differ from FFmpeg')
        words = [1, got['frame_log'], 0, got['poc_log'], 0, got['frame_mbs_only'], got['direct_8x8'],
                 got['width']//16, got['height']//16, got['entropy'], got['bottom_poc'], 0, 0, 0,
                 got['l0'], got['l1'], got['weighted'], got['bipred'], got['qp'] & 0xffffffff,
                 got['deblock'], got['redundant'], 0, 0]
        picture = b''.join(struct.pack('<I', x) for x in words) + bytes(32)
        staged = output.read_bytes(); payload = annex_sample(sample.read_bytes())
        need(staged[:124] == picture and staged[0x700:0x700+len(payload)] == payload and
             staged[0x700+len(payload):] == bytes.fromhex('0000010b000000000000010b00000000') and
             struct.unpack_from('<I', staged, 0x100)[0] == len(payload)+16, 'staged output differs')
        rows.append({'frame':i, 'slice_count':got['slice_count'], 'frame_num':got['frame_num'],
                     'first_macroblocks':got['first_macroblocks'], 'staged_sha256':sha(output)})
    result = {'status':'PASS_SIX_FFMPEG_BASELINE_HEADERS_CPU', 'frames':6, 'slice_headers':12,
        'fixture_annex_sha256':FIXTURE_SHA, 'reference_receipt_sha256':sha(a.reference/'receipt.json'),
        'reference_binary_sha256':receipt['binary_sha256_before_after'], 'reference_version':receipt['ffmpeg_version'],
        'reference_trace_sha256':receipt['trace_sha256'], 'source_sha256':{n:sha(HERE/n) for n in
            ('H264Stream.cpp','H264Stream.h','H264Baseline.cpp','H264Baseline.h','VideoLayout.cpp','VideoLayout.h',
             'baseline_tool.cpp','test_baseline.cpp','validate_baseline.py')},
        'rows':rows, 'reference_stage_comparison':True, 'vui_parsed':False, 'complete_slice_parsed':False,
        'gpu_transport_implemented':False, 'hardware_video_execution_proved':False, 'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))


if __name__ == '__main__': main()
