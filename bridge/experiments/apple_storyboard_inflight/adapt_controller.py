#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Locally adapt the exact controller from the separately obtained Apple sample."""
from pathlib import Path
import hashlib

CONTROLLER_HASHES = {
    'AAPLViewController.m':'c77b3bcf6babfc5c4d180c636abf0985595cb208bf79043951a93c88994b5970',
    'AAPLViewController.h':'dbf1a0d311e41205ac2c90ca473d79141c404784fdfd2ff560d86dc5ed6a44ad',
    'macOS/Base.lproj/Main.storyboard':'2260b7d84632cf2378792554cbc7bc02d36af80009bd5e97c8d2b868b766e926',
}
def adapt_controller(source, target):
    for name,digest in CONTROLLER_HASHES.items():
        if hashlib.sha256((source/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Apple controller/storyboard hash differs: '+name)
    (target/'AAPLViewController.h').write_bytes((source/'AAPLViewController.h').read_bytes())
    s=(source/'AAPLViewController.m').read_text()
    old='_view.device = MTLCreateSystemDefaultDevice();'
    new='''_view.device = MTLCreateSystemDefaultDevice();
    NSAssert([_view.device.name isEqual:@"NVIDIA GeForce GTX 880M"], @"Unexpected GPU");
    _view.paused=YES; _view.enableSetNeedsDisplay=NO; _view.framebufferOnly=NO;
    _view.autoResizeDrawable=NO; _view.drawableSize=CGSizeMake(64,48);'''
    if s.count(old)!=1:raise ValueError('device anchor differs')
    s=s.replace(old,new)
    old='NSAssert(supportICB, @"Sample requires macOS_GPUFamily2_v1 or iOS_GPUFamily3_v4 for Indirect Command Buffers");'
    new='''// Lab opt-in only; preserve the observed family result and do not spoof MTLDevice.
    NSLog(@"KeplerMetal lab: native ICB family gate = %@", supportICB ? @"YES" : @"NO");'''
    if s.count(old)!=1:raise ValueError('family gate anchor differs')
    (target/'AAPLViewController.m').write_text(s.replace(old,new))
