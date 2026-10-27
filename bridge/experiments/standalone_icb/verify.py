#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent, offline oracle for a completed standalone experiment."""
from pathlib import Path
import hashlib, json, math, struct, sys

def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(path):
    p = Path(path).resolve()
    inputs, host = read(p/'inputs.json'), read(p/'execution/manifest.json')
    mode = inputs['mode']
    assert mode in ('direct','auto','auto-native','wrong-library','wrong-client')
    expected = 3 if mode == 'wrong-client' else 7 if mode in ('auto-native','wrong-library') else 0
    reservation = host['GPU_reservation']
    assert host['exit_code'] == expected and not host['SIGKILL_requested'] and not host['authoritative_ps_status']
    assert reservation['state'] == 'terminal' and reservation['exit_code'] == expected
    assert reservation['child_PID'] == host['pid'] and not reservation['known_signed_processes_live']
    assert sha(p/'application') == inputs['run_executable_SHA256'] == host['original_binary_sha256']
    assert sha(p/'execution/application') == host['signed_binary_sha256'] == reservation['signed_binary_sha256']
    for name,digest in inputs['frozen'].items(): assert sha(p/name) == digest, name
    assert host['launcher_SHA256'] == inputs['frozen']['runtime/run_host.py']
    assert host['reservation_module_SHA256'] == inputs['frozen']['runtime/lab_gpu_reservation.py']
    injected = mode in ('auto','wrong-library','wrong-client')
    assert host['injected_library_SHA256'] == (inputs['frozen']['assets/bootstrap.dylib'] if injected else None)
    app = read(p/'execution/execution.stdout') if mode != 'wrong-client' else None
    if app:
        assert app['device'] == 'NVIDIA GeForce GTX 880M' and app['registry_id'] != 0
    client = app['client'] if app else None
    trace = (p/'execution/execution.stderr').read_text()
    expected_library = 'wrong_carrier.metallib' if mode == 'wrong-library' else 'carrier.metallib'
    assert host['arguments'] == [str(p/'assets'/expected_library),str(p/'outputs'),'direct' if mode=='direct' else 'auto']
    if mode in ('direct','auto'):
        assert client['status'] == 'PASS' and client['command_status'] == 4
        assert client['did_execute_icb'] == (mode == 'auto')
        assert client['used_standard_direct_draw'] == (mode == 'direct')
        assert (client['width'],client['height'],client['frames']) == (64,48,1)
        image = (p/'outputs/frame-0.bin').read_bytes()
        assert len(image) == 64*48*16+512 and image[:256] == image[-256:] == b'\xa5'*256
        values = struct.unpack('<%df' % (64*48*4), image[256:-256])
        expected_color = (.75,.125,.25,1.)
        assert all(math.isfinite(v) and v == expected_color[i%4] for i,v in enumerate(values))
        assert sha(p/'outputs/frame-0.bin') == 'ad54a279b3c738206061e86dc4598c2675204b2fb3b9d4461821b1f5524da7fc'
    else:
        assert not (p/'outputs/frame-0.bin').exists()
    if mode == 'auto':
        assert all(s in trace for s in ('KM_BOOT enabled','KM_BOOT queue matched','KM_BOOT library snapshot approved','KM_BOOT pipeline matched'))
        assert app['device_class'].startswith('KPICBDevice_') and app['queue_class'].startswith('KPAutomaticQueue_')
        assert client['command_buffer_class'].startswith('KPAutomaticCommandBuffer_') and client['render_encoder_classes'][0].startswith('KPICBRenderEncoder_')
        events = read(p/'events.json')
        executed = [e for e in events if e['operation'] == 'execute_CPU_render_ICB']
        assert len(executed) == 1 and executed[0]['executed_indices'] == [0] and not executed[0]['full_ICB_contract']
    elif mode == 'direct':
        assert not trace and app['device_class'] == 'NVMTLDevice' and app['queue_class'] == 'NVMTLCommandQueue'
    elif mode == 'auto-native':
        assert not trace and 'newIndirectCommandBufferWithDescriptor:maxCount:options:' in client['failure'] and 'unrecognized selector' in client['failure']
    elif mode == 'wrong-client':
        assert inputs['run_executable_SHA256'] != inputs['executable_SHA256']
        assert 'KM_BOOT identity refused' in trace and 'KM_BOOT enabled' not in trace
        assert not (p/'events.json').exists() and not (p/'execution/execution.stdout').read_text()
    else:
        assert 'KM_BOOT library unapproved' in trace and 'KM_BOOT pipeline matched' not in trace
        assert client['failure'] == 'Render pipeline is not owned by this scope'
        assert not any(e['operation'] == 'execute_CPU_render_ICB' for e in read(p/'events.json'))
    return {'status':'PASS','mode':mode,'process_exit':expected,'gpu_pixels_checked':64*48*4 if mode in ('direct','auto') else 0,'scope':'one signed experimental client and one library','general_application_compatibility':False,'system_modified':False}

if __name__ == '__main__': print(json.dumps(verify(sys.argv[1]),sort_keys=True))
