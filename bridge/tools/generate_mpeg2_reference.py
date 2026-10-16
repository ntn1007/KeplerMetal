#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create a bounded MPEG2 fixture and independent software reference with FFmpeg.

Requires existing, explicitly pinned FFmpeg/ffprobe executables. Installs nothing
and selects software codec/filter paths only. No NVIDIA/macOS binary is copied.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import platform
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', type=Path, required=True)
    parser.add_argument('--ffprobe', type=Path, required=True)
    parser.add_argument('--expected-ffmpeg', required=True)
    parser.add_argument('--expected-ffprobe', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    for binary, expected in [(args.ffmpeg, args.expected_ffmpeg), (args.ffprobe, args.expected_ffprobe)]:
        if sha(binary) != expected:
            raise ValueError('Tool does not match the explicitly selected binary')
    out = args.out.resolve()
    out.mkdir(exist_ok=False)
    fixture = out / 'fixture'
    fixture.mkdir()
    records = []

    def run(label, argv):
        with (out / (label + '.stdout')).open('xb') as stdout, (out / (label + '.stderr')).open('xb') as stderr:
            child = subprocess.Popen(list(map(str, argv)), stdout=stdout, stderr=stderr)
            record = {'label': label, 'argv': list(map(str, argv)), 'pid': child.pid,
                'started_at': datetime.datetime.now(datetime.timezone.utc).isoformat()}
            records.append(record)
            write(out / 'commands.json', records)
            killed = False
            try:
                code = child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                child.kill()
                killed = True
                code = child.wait(timeout=5)
        ps = subprocess.run(['ps', '-o', 'pid=,lstart=,command=', '-p', str(child.pid)],
                            capture_output=True, text=True, timeout=5).stdout.strip()
        record.update(exit_code=code, SIGKILL_requested=killed, authoritative_ps_status=ps,
            completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            stdout_SHA256=sha(out / (label + '.stdout')), stderr_SHA256=sha(out / (label + '.stderr')))
        write(out / 'commands.json', records)
        if code or killed or ps:
            raise RuntimeError(label + ': inspect the retained process receipt')

    width, height, count = 320, 240, 6
    raw = bytearray()
    # Constant 16x16 macroblocks avoid unnecessary IDCT variability while still
    # exercising nonconstant images, chroma, frame ordering and six fresh frames.
    for frame in range(count):
        for y in range(height):
            for x in range(width):
                raw.append(16 + 8 * ((x // 16 + 3 * (y // 16) + 5 * frame) % 27))
        for y in range(height // 2):
            for x in range(0, width, 2):
                raw.extend((64 + 8 * ((x // 16 + y // 8 + frame) % 16),
                            64 + 8 * ((2 * (x // 16) + y // 8 + 3 * frame) % 16)))
    input_file = out / 'input.nv12'
    input_file.write_bytes(raw)
    video, decoded = out / 'fixture.m2v', out / 'decoded.nv12'
    base = [args.ffmpeg, '-hide_banner', '-nostdin', '-n', '-loglevel', 'verbose']
    run('encode', base + ['-hwaccel', 'none', '-f', 'rawvideo', '-pixel_format', 'nv12',
        '-video_size', '320x240', '-framerate', '30', '-i', input_file, '-filter_threads', '1',
        '-filter_complex_threads', '1', '-frames:v', '6', '-an', '-sn', '-dn', '-c:v', 'mpeg2video',
        '-pix_fmt', 'yuv420p', '-g', '1', '-bf', '0', '-q:v', '2', '-threads', '1', '-f', 'mpeg2video', video])
    run('decode', base + ['-hwaccel', 'none', '-c:v', 'mpeg2video', '-threads', '1', '-f', 'mpegvideo',
        '-i', video, '-filter_threads', '1', '-filter_complex_threads', '1', '-frames:v', '6',
        '-an', '-sn', '-dn', '-c:v', 'rawvideo', '-pix_fmt', 'nv12', '-threads', '1', '-f', 'rawvideo', decoded])
    run('packets', [args.ffprobe, '-hide_banner', '-loglevel', 'error', '-f', 'mpegvideo',
        '-show_streams', '-show_packets', '-show_data_hash', 'sha256', '-of', 'json', video])
    data, pixels = video.read_bytes(), decoded.read_bytes()
    probe = json.loads((out / 'packets.stdout').read_text())
    packets, streams = probe['packets'], probe['streams']
    if len(packets) != 6 or len(pixels) != 691200 or len(streams) != 1 or streams[0]['codec_name'] != 'mpeg2video':
        raise ValueError('Unexpected codec, packet or decoded image count')
    if (streams[0]['width'], streams[0]['height']) != (width, height):
        raise ValueError('Wrong dimensions')
    frames, offset = [], 0
    for i, packet in enumerate(packets):
        start, size = int(packet['pos']), int(packet['size'])
        payload = data[start:start + size]
        if start != offset or len(payload) != size or 'K' not in packet['flags']:
            raise ValueError('Expected contiguous independently decodable packet boundaries')
        digest = hashlib.sha256(payload).hexdigest()
        if packet['data_hash'].lower() != 'sha256:' + digest:
            raise ValueError('Packet hash differs from independently parsed file region')
        name = 'frame-%03d.m2v' % i
        (fixture / name).write_bytes(payload)
        (fixture / ('cpu-frame-%03d.nv12' % i)).write_bytes(pixels[i * 115200:(i + 1) * 115200])
        frames.append({'file': name, 'bytes': size, 'SHA256': digest, 'pts_value': i, 'pts_scale': 30})
        offset += size
    if offset != len(data):
        raise ValueError('Unaccounted elementary-stream bytes')
    write(fixture / 'fixture.json', {'codec': 'MPEG2Video', 'width': width, 'height': height,
        'frames': frames, 'CPU_reference': 'Pinned FFmpeg native mpeg2video, hwaccel none',
        'CPU_reference_SHA256': sha(decoded), 'compressed_SHA256': sha(video)})
    for binary, expected in [(args.ffmpeg, args.expected_ffmpeg), (args.ffprobe, args.expected_ffprobe)]:
        if sha(binary) != expected:
            raise ValueError('Tool changed during execution')
    write(out / 'manifest.json', {'status': 'PASS', 'architecture': platform.machine(),
        'ffmpeg_SHA256': args.expected_ffmpeg, 'ffprobe_SHA256': args.expected_ffprobe,
        'input_SHA256': sha(input_file), 'compressed_SHA256': sha(video), 'decoded_SHA256': sha(decoded),
        'decoded_bytes': len(pixels), 'frames': count, 'packet_bytes': offset, 'hardware_acceleration': 'none',
        'performance_benchmark': False, 'system_modified': False,
        'fixture_files_SHA256': {p.name: sha(p) for p in fixture.iterdir()}, 'commands_SHA256': sha(out / 'commands.json')})
    print(json.dumps({'status': 'PASS', 'frames': count, 'decoded_bytes': len(pixels), 'hardware_acceleration': 'none'}))


if __name__ == '__main__':
    main()
