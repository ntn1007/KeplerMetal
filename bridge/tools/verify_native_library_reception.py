#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU receipt checks for ordinary native source library/function factories."""
LIBRARIES=['newLibraryWithData:error:','newLibraryWithURL:error:','newLibraryWithFile:error:']
FUNCTIONS=['newFunctionWithName:']+['newFunctionWithName:constantValues:error:']*3+['newFunctionWithDescriptor:error:']*3+['newFunctionWithName:constantValues:completionHandler:','newFunctionWithDescriptor:completionHandler:']
NAMES=['encode_dataflow_'+s for s in ['basic','barrier','copy','no_seed','no_gather','no_finish']]


def verify(d,inputs):
 assert d['native_library_factories']and inputs['native_library_factory_run']
 assert d['producer_backend']=='native_msl'and d['public_argument_encoder']and d['function_argument_encoder']and not d['argument_refusal_probe']
 le=d['library_reception'];l,f,p=map(int,inputs['library_route'].split(':'));assert le['route']==inputs['library_route']
 assert(le['library_factory'],le['function_factory'],le['pipeline_factory'])==(l,f,p)
 assert le['function_callbacks']==int(f>=7)and le['pipeline_callbacks']==int(p>=3)
 assert not le['manual_function_registrations']and not le['manual_compute_adaptations']
 assert le['native_library_restored']and le['native_queue_restored']
 tagged=d['producer_info']['generation_tagged_root'];assert bool(le['generation_tagged_root'])==bool(tagged)
 digest=inputs['assets_SHA256']['reusable_producer.metallib'if tagged else'native_producer.metallib']
 wanted=[85 if tagged else 60,85,60,60,60,60]
 assert le['returned_function']==d['producer_info']['function']==('alias_'+le['source_function']if f==6 else le['source_function'])
 assert le['pipeline_class']=='NVMTLComputePipelineState'and le['native_reflection']==(p not in [0,3])
 assert le['pipeline_members']==([dict(index=i,type=t,offset=i*8)for i,t in enumerate(wanted)]if p not in [0,3]else[])
 events=d['function_events'];find=lambda op:[e for e in events if e.get('operation')==op]
 reg=find('register_native_source_IRv2_library');assert len(reg)==1;e=reg[0]
 assert e['source_SHA256']==digest and e['functions']==NAMES and e['prepared_native_pipelines']==6
 assert bool(e['generation_tagged_root'])==bool(tagged)and not e['instruction_import']and e['native_pipeline_factories_preserved']and not e['GPU_execution']
 libraries=find('automatic_IRv2_library');assert len(libraries)==1 and libraries[0]['selector']==LIBRARIES[l]and libraries[0]['source_SHA256']==digest
 functions=find('automatic_IRv2_function');assert 1<=len(functions)<=3
 assert functions[-1]['selector']==FUNCTIONS[f]and functions[-1]['returned_function']==le['returned_function']
 # Native descriptor/async implementations may forward through the plain-name
 # public selector. These automatic intermediate functions are not extra callbacks.
 for e in functions:
  assert e['selector']in {FUNCTIONS[f],'newFunctionWithName:'}and e['source_function']==le['source_function']and e['returned_function']in {le['source_function'],le['returned_function']}and e['library_SHA256']==digest
  assert e['native_function']and e['native_source_lowering']and bool(e['generation_tagged_root'])==bool(tagged)and not e['pipeline_imports_during_lookup']
 native=find('register_native_IRv2_function');assert 1<=len(native)<=len(functions)
 for e in native:
  schema=e['schema'];assert e['library_SHA256']==digest and not e['native_shader_compilation_replaced']and not e['GPU_execution']
  assert schema['buffer_index']==0 and schema['binding_count']==4 and schema['encoded_length']==48 and schema['alignment']==8
  assert [(m['type'],m['offset'],m['index'])for m in schema['members']]==[(t,i*8,i)for i,t in enumerate(wanted)]
 getters=find('function_IRv2_argument_encoder');assert len(getters)==(2 if tagged or d['mode']=='encoder_reuse'else 5)
 assert all(e.get('native_reflection_preserved')for e in getters if e['reflection_requested'])
 assert len(find('automatic_compute_factories_enabled'))==1
 assert len(find('automatic_command_buffer'))>=4 and len(find('automatic_compute_encoder'))>=4
 assert all(not e['explicit_adaptation_required']for e in find('automatic_compute_encoder'))
 for op in ['restore_IRv2_functions','restore_IRv2_libraries','automatic_compute_factories_restored']:assert len(find(op))==1
 assert 1<=find('restore_IRv2_functions')[0]['live_functions_restored']<=len(native) and find('restore_IRv2_libraries')[0]['live_libraries_restored']==1
 for op in ['register_native_source_IRv2_function','register_native_IRv2_producer','new_registered_IRv2_pipeline','IRv2_pipeline_contract_request']:assert not find(op)
 for r in d['runs']:
  encoded=[e for e in r['events']if e.get('operation')=='encode_public_IRv2_arguments'];assert len(encoded)==4 and all(e['bytes']==48 and not e['native_Apple_ICB_identity']for e in encoded)
 return dict(native_library_factories=True,library_route=inputs['library_route'],manual_function_registrations=0,manual_compute_adaptations=0,native_pipeline_factories_preserved=True,automatic_function_adoptions=len(native),native_forwarded_function_calls=len(functions)-1)
