#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild the four existing pinned command shaders from public project source.

No downloads, driver payloads, GPU submissions or automatic pin updates.
"""
from pathlib import Path
import argparse
import shutil
from public_large_scratch import ROOT,commands,preflight,read,sha,write


def build(out):
    out=out.resolve();preflight(out);out.mkdir();src=out/'src';src.mkdir()
    names=['gpu_command_selector','gpu_command_geometry','gpu_command_bindings']
    for name in names:shutil.copyfile(ROOT/'src'/(name+'.metal'),src/(name+'.metal'))
    # Preserve the historical compiler input basename of the v2 materializer.
    shutil.copyfile(ROOT/'src/command_ir_materializer_v2.metal',src/'command_ir_materializer.metal')
    shutil.copyfile(Path(__file__),src/'build_gpu_icb_texture_assets.py')
    shutil.copyfile(ROOT/'tools/native_msl_fixture_pins.json',src/'native_msl_fixture_pins.json')
    pins=read(src/'native_msl_fixture_pins.json')['assets'];run=commands(out);rows=[]
    for name in names+['materializer']:
        source='command_ir_materializer'if name=='materializer'else name
        run(name+'-metal',['xcrun','-sdk','macosx','metal','-std=macos-metal2.0','-I',src,'-c',src/(source+'.metal'),'-o',out/(name+'.air')])
        run(name+'-metallib',['xcrun','-sdk','macosx','metallib',out/(name+'.air'),'-o',out/(name+'.metallib')])
        actual=sha(out/(name+'.metallib'));rows.append(dict(name=name+'.metallib',SHA256=actual,expected_SHA256=pins[name+'.metallib'],match=actual==pins[name+'.metallib']))
    ok=all(r['match']for r in rows)
    write(out/'manifest.json',dict(status='PASS_PIN_MATCH'if ok else'FAIL_PIN_MISMATCH',GPU_execution=False,SDK_modified=False,
        source_SHA256={p.name:sha(p)for p in src.iterdir()},assets=rows))
    assert ok,'A different shader build needs separate qualification; no pin was changed'
    print('Four public-source shader builds match the existing qualified pins.')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build(a.out)
