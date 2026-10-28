// SPDX-License-Identifier: MIT
// Test-process-only guard; not a runtime cancellation API.
#import <objc/message.h>
static void witnessReject(id,SEL s){[NSException raise:@"KPPlanRevokeWitness" format:@"%@ refused",NSStringFromSelector(s)];}
static bool witnessBlock(id cb,SEL s){@try{((void(*)(id,SEL))objc_msgSend)(cb,s);}@catch(NSException*x){return [x.name isEqual:@"KPPlanRevokeWitness"];}return false;}
static bool witnessRevoke(id<MTLCommandBuffer> cb){
 Class base=object_getClass(cb);if(!cb||base!=objc_getClass("NVMTLCommandBuffer")||class_getInstanceSize(base)!=656||cb.status!=MTLCommandBufferStatusNotEnqueued||!cb.retainedReferences)return false;
 Method a=class_getInstanceMethod(base,@selector(commit)),b=class_getInstanceMethod(base,@selector(enqueue));if(!a||!b||!method_getTypeEncoding(a)||!method_getTypeEncoding(b)||strcmp(method_getTypeEncoding(a),"v16@0:8")||strcmp(method_getTypeEncoding(b),"v16@0:8"))return false;
 NSString*n=[@"KPPlanWitness_" stringByAppendingString:[NSUUID.UUID.UUIDString stringByReplacingOccurrencesOfString:@"-" withString:@""]];Class sub=objc_allocateClassPair(base,n.UTF8String,0);if(!sub)return false;
 if(!class_addMethod(sub,@selector(commit),(IMP)witnessReject,method_getTypeEncoding(a))||!class_addMethod(sub,@selector(enqueue),(IMP)witnessReject,method_getTypeEncoding(b))){objc_disposeClassPair(sub);return false;}
 objc_registerClassPair(sub);if(class_getInstanceSize(sub)!=class_getInstanceSize(base))return false;object_setClass(cb,sub);return object_getClass(cb)==sub;
}
