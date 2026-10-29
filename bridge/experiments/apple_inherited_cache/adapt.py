#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply audited, exact-match local edits to the pinned Apple renderer.

Apple's source is obtained separately and is neither included nor distributed.
"""
import hashlib
from pathlib import Path

EXPECTED = {
    'AAPLRenderer.m': '124bb0bb75b7961ebfe3d7e5fd41bbeec2c7c4d74c5f3a9fb211ec017f58c230',
    'AAPLRenderer.h': '9507af071733eba63c43ca787f1e5fb25516a38877eb7844376923b678f4373a',
    'AAPLShaderTypes.h': '7f6b70576fb1e00422520f273530fd55e4fe5036c42b11bdf74205bae64609a2',
}

def adapt(source, target):
    for name, digest in EXPECTED.items():
        data = (source/name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Apple source hash differs: '+name)
        if name != 'AAPLRenderer.m':
            (target/name).write_bytes(data)
    s = (source/'AAPLRenderer.m').read_text()
    def replace(old, new):
        nonlocal s
        if s.count(old) != 1:
            raise ValueError('Expected one source anchor: '+old[:90])
        s=s.replace(old,new,1)
    replace('#import "AAPLRenderer.h"', '''#import "AAPLRenderer.h"
#import "KeplerCPUICB.h"
extern NSString *KMMode, *KMLegacy, *KMShader, *KMManifest, *KMOutput;
extern KPCPUICBScope *KMScope;
extern NSMutableArray *KMFrames, *KMDepthActions, *KMSubmittedCBs;
extern NSInteger KMRefusals, KMBindingRefusals;
extern BOOL KMActive;''')
    replace('id <MTLLibrary> defaultLibrary = [_device newDefaultLibrary];', 'id <MTLLibrary> defaultLibrary = [_device newLibraryWithFile:KMShader error:nil];')
    replace('pipelineStateDescriptor.supportIndirectCommandBuffers = TRUE;', 'pipelineStateDescriptor.supportIndirectCommandBuffers = NO;')
    replace('_renderPipelineState = [_device newRenderPipelineStateWithDescriptor:pipelineStateDescriptor error:&error];', '''if ([KMMode isEqual:@"auto"]) {
            NSData *carrier=[NSData dataWithContentsOfFile:KMLegacy], *library=[NSData dataWithContentsOfFile:KMShader], *manifest=[NSData dataWithContentsOfFile:KMManifest];
            KMScope=[KPCPUICBScope installRenderingOnDevice:_device queue:_commandQueue libraryData:carrier expectedSHA256:@"965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7" error:&error];
            NSCAssert(KMScope && [KMScope registerRenderVertexLibraryData:library expectedSHA256:@"adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf" manifestData:manifest expectedManifestSHA256:@"6930ed313d2e1b1e836f189afb2db7c0286f10afb9c867ec3fe9659390e16732" error:&error], @"adapter registration: %@", error);
            _renderPipelineState=[KMScope renderPipelineForName:@"apple_explicit_view"];
        } else _renderPipelineState = [_device newRenderPipelineStateWithDescriptor:pipelineStateDescriptor error:&error];''')
    replace('        _indirectCommandBuffer = [_device newIndirectCommandBufferWithDescriptor:icbDescriptor', '        if ([KMMode isEqual:@"auto"]) {\n        _indirectCommandBuffer = [_device newIndirectCommandBufferWithDescriptor:icbDescriptor')
    replace('    return self;\n}', '    return self;\n}') # exact anchor sanity only
    replace('    }\n\n    return self;\n}', '        }\n    }\n\n    return self;\n}')
    replace('id <MTLRenderCommandEncoder> renderEncoder =\n            [commandBuffer renderCommandEncoderWithDescriptor:renderPassDescriptor];', '''renderPassDescriptor.colorAttachments[0].storeAction=MTLStoreActionStore;
        NSCAssert(renderPassDescriptor.depthAttachment.loadAction==MTLLoadActionClear && renderPassDescriptor.depthAttachment.storeAction==MTLStoreActionDontCare, @"unexpected MTKView depth actions");
        [KMDepthActions addObject:@(renderPassDescriptor.depthAttachment.storeAction)];
        NSError *adapterError=nil;
        if ([KMMode isEqual:@"auto"]) {
            MTLRenderPassDescriptor *invalid=[renderPassDescriptor copy];
            invalid.depthAttachment.storeAction=MTLStoreActionMultisampleResolve;
            id<MTLRenderCommandEncoder> rejected=[KMScope renderEncoderWithDescriptor:invalid commandBuffer:commandBuffer error:&adapterError];
            NSCAssert(!rejected && [adapterError.localizedDescription isEqual:@"Depth attachment outside qualified profile"] && commandBuffer.status==MTLCommandBufferStatusNotEnqueued, @"invalid depth action was not refused before user commit");
            KMRefusals++;
            adapterError=nil;
        }
        id <MTLRenderCommandEncoder> renderEncoder = [KMMode isEqual:@"auto"] ? [KMScope renderEncoderWithDescriptor:renderPassDescriptor commandBuffer:commandBuffer error:&adapterError] : [commandBuffer renderCommandEncoderWithDescriptor:renderPassDescriptor];
        NSCAssert(renderEncoder, @"encoder: %@",adapterError);''')
    replace('[renderEncoder executeCommandsInBuffer:_indirectCommandBuffer withRange:NSMakeRange(0, AAPLNumObjects)];', '''if ([KMMode isEqual:@"auto"]) {
            if (_frameNumber==5) {
                id<MTLIndirectRenderCommand> changed=[_indirectCommandBuffer indirectRenderCommandAtIndex:0];
                id<MTLBuffer> shortBuffer=[_device newBufferWithLength:16 options:MTLResourceStorageModeShared];
                [changed setVertexBuffer:shortBuffer offset:0 atIndex:AAPLVertexBufferIndexVertices];
                BOOL refused=NO;
                @try { [renderEncoder executeCommandsInBuffer:_indirectCommandBuffer withRange:NSMakeRange(0, AAPLNumObjects)]; }
                @catch (NSException *x) { refused=[x.name isEqual:@"KeplerCPUICBUnsupported"] && [x.reason isEqual:@"Apple explicit buffer range or alignment differs"]; }
                NSCAssert(refused && commandBuffer.status==MTLCommandBufferStatusNotEnqueued, @"short rebound buffer was not refused before user commit");
                KMBindingRefusals++;
                [changed setVertexBuffer:_vertexBuffer[1] offset:0 atIndex:AAPLVertexBufferIndexVertices];
            }
            [renderEncoder executeCommandsInBuffer:_indirectCommandBuffer withRange:NSMakeRange(0, AAPLNumObjects)];
        }
        else if ([KMMode isEqual:@"direct"]) for (int i=0;i<AAPLNumObjects;i++) {
            [renderEncoder setVertexBuffer:(i==0 && _frameNumber>=5)?_vertexBuffer[1]:_vertexBuffer[i] offset:0 atIndex:AAPLVertexBufferIndexVertices];
            [renderEncoder setVertexBuffer:_objectParameters offset:0 atIndex:AAPLVertexBufferIndexObjectParams];
            [renderEncoder setVertexBuffer:_indirectFrameStateBuffer offset:0 atIndex:AAPLVertexBufferIndexFrameState];
            [renderEncoder drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:_vertexBuffer[i].length/sizeof(AAPLVertex) instanceCount:1 baseInstance:i];
        }''')
    replace('        // Schedule a present once the framebuffer is complete using the current drawable', '''        id<MTLTexture> target=renderPassDescriptor.colorAttachments[0].texture;
        NSCAssert(target && !target.framebufferOnly && target.width==64 && target.height==48, @"capture target differs target=%@ framebuffer=%d width=%lu height=%lu",target,target.framebufferOnly,(unsigned long)target.width,(unsigned long)target.height);
        id<MTLBuffer> capture=[_device newBufferWithLength:12800 options:MTLResourceStorageModeShared];
        memset(capture.contents,0xa5,capture.length);
        id<MTLBlitCommandEncoder> captureEncoder=[commandBuffer blitCommandEncoder];
        [captureEncoder copyFromTexture:target sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(64,48,1) toBuffer:capture destinationOffset:256 destinationBytesPerRow:256 destinationBytesPerImage:12288];
        [captureEncoder endEncoding];
        [KMFrames addObject:capture];
        // Schedule a present once the framebuffer is complete using the current drawable''')
    replace('- (void) drawInMTKView:(nonnull MTKView *)view\n{', '- (void) drawInMTKView:(nonnull MTKView *)view\n{ if (!KMActive) return;')
    replace('    [commandBuffer commit];\n}', '''    [commandBuffer commit];
    [KMSubmittedCBs addObject:commandBuffer];
}''')
    (target/'AAPLRenderer.m').write_text(s)
