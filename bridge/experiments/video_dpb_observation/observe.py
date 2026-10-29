#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare a pinned software decoder's short-term snapshots with CPU VP proposals."""
import argparse
import hashlib
import json
import re
import shlex
import struct
import subprocess
from pathlib import Path, PurePosixPath

FF_SHA = '7f6028378534aa10a2dfa07d807ddcc0d18c869bf5c2f64c89efcc18ee88c4ee'
FIX_SHA = '12858642f02b0e1d98ddf409dd729a879b6a7a5d3434c860882532ca4f6b40af'
REFERENCE_SHA = 'd73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1'
SSH = ['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8']
PREFIX = re.compile(r'^\[h264 @ (0x[0-9a-f]+)\] (.*)$')
REF = re.compile(r'^(\d+) fn:(-?\d+) poc:(-?\d+) (0x[0-9a-f]+)$')
SLICE = re.compile(r'^slice:(\d+) F mb:(\d+) (I IDR|P) frame:(\d+) poc:(-?\d+)/(-?\d+) ref:(\d+)/(\d+) ')


def need(ok, message):
    if not ok: raise ValueError(message)


def sha(data): return hashlib.sha256(data).hexdigest()


def snapshots(log):
    states = {}; rows = []
    for line in log.splitlines():
        match = PREFIX.match(line)
        if not match: continue
        ctx, msg = match.groups()
        if msg == 'short term list:': states[ctx] = {'phase':'short', 'short':[], 'long':[]}; continue
        state = states.get(ctx)
        if not state: continue
        if msg == 'long term list:': state['phase'] = 'long'; continue
        entry = REF.match(msg)
        if entry and state['phase'] in ('short','long'):
            index, frame, poc, pointer = entry.groups()
            state[state['phase']].append((int(index), int(frame), int(poc), pointer))
            continue
        slice_match = SLICE.match(msg)
        if slice_match and state['phase'] == 'long':
            n, mb, kind, frame, top, bottom, l0, l1 = slice_match.groups()
            rows.append({'context':ctx, 'slice':int(n), 'mb':int(mb), 'kind':kind,
                         'frame':int(frame), 'top':int(top), 'bottom':int(bottom),
                         'l0':int(l0), 'l1':int(l1), 'short':state['short'], 'long':state['long']})
            state['phase'] = 'consumed'
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True);p.add_argument('--remote-ffmpeg',required=True)
    p.add_argument('--remote-fixture',required=True);p.add_argument('--predictive',type=Path,required=True)
    p.add_argument('--reference-nv12',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    need(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',a.host),'invalid host')
    for path in (a.remote_ffmpeg,a.remote_fixture):
        need(path.startswith('/') and not any(x in path for x in '\n\r\0') and '..' not in PurePosixPath(path).parts,'invalid path')
    need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    predfile=a.predictive/'validation.json'; pred=json.loads(predfile.read_text())
    need(pred['status']=='PASS_FIVE_BASELINE_P_PROPOSALS_CPU' and len(pred['rows'])==5,'predictive receipt differs')
    blocks=[]
    for i,row in enumerate(pred['rows'],1):
        data=(a.predictive/('p-%03d.bin'%i)).read_bytes()
        need(row['frame']==i and len(data)==756 and sha(data)==row['block_sha256'],'proposal differs')
        count=row['reference_count']; need(count==(1 if i==1 else 2),'count differs')
        blocks.append({'frame':i,'references':[struct.unpack_from('<I',data,0x4c+16*j)[0] for j in range(count)],
                       'poc':struct.unpack_from('<I',data,0x38)[0]})
    reference=a.reference_nv12.read_bytes();need(len(reference)==691200 and sha(reference)==REFERENCE_SHA,'pixel reference differs')
    a.out.mkdir(); ff=shlex.quote(a.remote_ffmpeg); fixture=shlex.quote(a.remote_fixture)
    identity='uname -m; '+ff+' -version | head -1; shasum -a 256 '+ff+' '+fixture
    decode=ff+' -hide_banner -nostdin -loglevel debug -hwaccel none -c:v h264 -threads 1 -debug mmco+pict -f h264 -i '+fixture+' -map 0:v:0 -f framehash -'
    def call(label,cmd):
        r=subprocess.run([*SSH,a.host,cmd],capture_output=True,timeout=120)
        (a.out/(label+'.stdout')).write_bytes(r.stdout);(a.out/(label+'.stderr')).write_bytes(r.stderr)
        need(r.returncode==0,label+' failed'); return r
    before=call('before',identity); decoding=call('decode',decode);after=call('after',identity)
    lines=before.stdout.decode().splitlines();need(before.stdout==after.stdout and len(lines)==4 and lines[0]=='arm64' and lines[1].startswith('ffmpeg version 9.0.2 '),'identity differs')
    need(lines[2].split(None,1)==[FF_SHA,a.remote_ffmpeg] and lines[3].split(None,1)==[FIX_SHA,a.remote_fixture],'pinned inputs differ')
    log=decoding.stderr.decode(); raw=decoding.stdout.decode()
    need('6 frames decoded; 0 decode errors' in log and 'Format yuv420p chosen' in log,'software decode incomplete')
    need('#hash: SHA256' in raw and '#dimensions 0: 320x240' in raw,'framehash format differs')
    fhash=re.findall(r'^0,\s*(\d+),\s*(\d+),\s*1,\s*115200,\s*([0-9a-f]{64})$',raw,re.M)
    need(len(fhash)==6 and [int(x[1]) for x in fhash]==list(range(6)),'frame hashes differ')
    for i,(_,_,digest) in enumerate(fhash):
        nv12=reference[115200*i:115200*(i+1)];y=320*240
        need(sha(nv12[:y]+nv12[y::2]+nv12[y+1::2])==digest,'software pixel reference differs')
    need(log.count('After avformat_find_stream_info()')==1,'stream-probe marker differs')
    # Ignore the separate probing decoder; associate snapshots with the later
    # decoding context that emits the six output frames.
    observations=snapshots(log.split('After avformat_find_stream_info()',1)[1]);need(len(observations)==12 and len({x['context'] for x in observations})==1,'slice snapshots differ')
    summary=[]
    for frame in range(6):
        pair=observations[2*frame:2*frame+2]
        need([x['frame'] for x in pair]==[frame]*2 and [x['slice'] for x in pair]==[1,2] and
             [x['mb'] for x in pair]==[0,150] and all(x['kind']==('I IDR' if frame==0 else 'P') and
             not x['long'] and x['top']==x['bottom']==65536+2*frame for x in pair),'slice metadata differs')
        expected=list(range(frame-1,max(-1,frame-3),-1));
        for x in pair:
            need([y[0] for y in x['short']]==list(range(len(expected))) and [y[1] for y in x['short']]==expected and
                 all(y[2]==65536+2*y[1] and y[3]!='0x0' for y in x['short']),'short-term list differs')
        if frame:
            b=blocks[frame-1];need(list(reversed(b['references']))==expected and b['poc']==2*frame,'proposal reference set differs')
            summary.append({'frame':frame,'short_refs_recent_first':expected,'proposal_refs_oldest_first':b['references'],
                            'ffmpeg_poc':pair[0]['top'],'proposal_poc':b['poc']})
    result={'status':'PASS_SOFTWARE_DPB_SNAPSHOTS','architecture':lines[0],'ffmpeg_version':lines[1],
            'ffmpeg_sha256':FF_SHA,'fixture_sha256':FIX_SHA,'ffmpeg_log_sha256':sha(decoding.stderr),
            'framehash_sha256':sha(decoding.stdout),'predictive_receipt_sha256':sha(predfile.read_bytes()),
            'source_sha256':sha(Path(__file__).read_bytes()),'frames_decoded':6,'slice_snapshots':12,
            'frame_hashes':[x[2] for x in fhash],'rows':summary,'long_term_refs_observed':False,
            'software_ffmpeg_poc_offset':65536,'same_ref_numbers_different_order':True,
            'pixel_reference_sha256':REFERENCE_SHA,'pixel_reference_separate_ffmpeg_binary':True,
            'pixel_reference_distinct_decoder_implementation':False,'all_six_pixels_match_reference':True,
            'hardware_ref_list_semantics_proved':False,
            'hardware_video_execution_proved':False,'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n'); print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
