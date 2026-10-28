// SPDX-License-Identifier: MIT
// Included only in an isolated modified copy of the dataflow client.
if(trial==0){
 witnessStale=[q commandBuffer];if(!witnessStale||![plan reserveCommandIRProducerInCommandBuffer:witnessStale error:&error])return 81;
 id<MTLComputeCommandEncoder>e=[witnessStale computeCommandEncoder];if(!e)return 82;
 [e setComputePipelineState:writer];[e setBuffer:root offset:0 atIndex:0];
 for(id<MTLBuffer>r in plan.commandIRProducerResources)[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];
 [e dispatchThreadgroups:MTLSizeMake(1,1,1) threadsPerThreadgroup:MTLSizeMake(32,1,1)];[e endEncoding];
 BOOL busyRefused=NO;@try{[target resetWithRange:NSMakeRange(0,rows)];}@catch(NSException*x){busyRefused=[x.reason containsString:@"uncompleted"];}
 if(!busyRefused)return 83;
 id lease=[plan valueForKey:@"reusableContext"];NSMutableDictionary*pending=[lease valueForKey:@"pending"];NSValue*key=[NSValue valueWithPointer:(__bridge const void*)witnessStale];
 if(!lease||pending.count!=1||pending[key]!=witnessStale||!witnessRevoke(witnessStale))return 84;
 if(!witnessBlock(witnessStale,@selector(commit))||!witnessBlock(witnessStale,@selector(enqueue))||witnessStale.status!=MTLCommandBufferStatusNotEnqueued)return 85;
 // Manual, test-only intervention. No production API exposes this operation.
 [pending removeObjectForKey:key];if(pending.count||[plan valueForKey:@"producerBuffer"]!=witnessStale)return 86;
 // A real plan also pins its producer independently of the lease dictionary.
 // Clear only this known, unsubmitted producer in this isolated test process.
 [plan setValue:nil forKey:@"producerBuffer"];if([plan valueForKey:@"producerBuffer"])return 86;
 witnessGeneration=[[plan valueForKey:@"reusableGeneration"]unsignedIntValue];witnessPrepared=YES;
}
