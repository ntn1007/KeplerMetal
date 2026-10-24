"""Receipt falsification controls, separate from Metal hardware reception."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_native_library_reception import verify,LIBRARIES,FUNCTIONS,NAMES


def fixture(tagged=False,route='0:0:0'):
 l,f,p=map(int,route.split(':'));types=[85 if tagged else 60,85,60,60,60,60]
 schema=dict(buffer_index=0,binding_count=4,encoded_length=48,alignment=8,members=[dict(type=t,index=i,offset=i*8)for i,t in enumerate(types)])
 name=NAMES[0];returned='alias_'+name if f==6 else name
 reg=dict(operation='register_native_source_IRv2_library',source_SHA256='digest',functions=NAMES,prepared_native_pipelines=6,generation_tagged_root=tagged,instruction_import=False,native_pipeline_factories_preserved=True,GPU_execution=False)
 events=[reg,dict(operation='automatic_IRv2_library',selector=LIBRARIES[l],source_SHA256='digest'),dict(operation='automatic_IRv2_function',selector=FUNCTIONS[f],source_function=name,returned_function=returned,library_SHA256='digest',native_function=True,native_source_lowering=True,generation_tagged_root=tagged,pipeline_imports_during_lookup=0),dict(operation='register_native_IRv2_function',library_SHA256='digest',native_shader_compilation_replaced=False,GPU_execution=False,schema=schema)]
 events +=[dict(operation='function_IRv2_argument_encoder',reflection_requested=False)for _ in range(2 if tagged else 5)]
 events +=[dict(operation='automatic_compute_factories_enabled')]+[dict(operation='automatic_command_buffer')for _ in range(4)]+[dict(operation='automatic_compute_encoder',explicit_adaptation_required=False)for _ in range(4)]
 events +=[dict(operation='restore_IRv2_functions',live_functions_restored=1),dict(operation='restore_IRv2_libraries',live_libraries_restored=1),dict(operation='automatic_compute_factories_restored')]
 le=dict(route=route,library_factory=l,function_factory=f,pipeline_factory=p,function_callbacks=int(f>=7),pipeline_callbacks=int(p>=3),manual_function_registrations=0,manual_compute_adaptations=0,native_library_restored=True,native_queue_restored=True,generation_tagged_root=tagged,source_function=name,returned_function=returned,pipeline_class='NVMTLComputePipelineState',native_reflection=p not in[0,3],pipeline_members=[dict(index=i,type=t,offset=i*8)for i,t in enumerate(types)]if p not in[0,3]else[])
 d=dict(native_library_factories=True,producer_backend='native_msl',public_argument_encoder=True,function_argument_encoder=True,argument_refusal_probe=False,library_reception=le,producer_info=dict(generation_tagged_root=tagged,function=returned),function_events=events,mode='basic',runs=[dict(events=[dict(operation='encode_public_IRv2_arguments',bytes=48,native_Apple_ICB_identity=False)for _ in range(4)])for _ in range(4)])
 return d,dict(native_library_factory_run=True,library_route=route,assets_SHA256={('reusable_producer.metallib'if tagged else'native_producer.metallib'):'digest'})


class NativeLibraryReceipts(unittest.TestCase):
 def test_pointer_and_generation_schemas_on_all_factory_routes(self):
  for tagged in [False,True]:
   for l in range(3):
    for f in range(9):
     for p in range(6):verify(*fixture(tagged,f'{l}:{f}:{p}'))
 def test_manual_registration_or_encoder_adaptation_invalidates_claim(self):
  for field in ['manual_function_registrations','manual_compute_adaptations']:
   d,i=fixture();d['library_reception'][field]=1
   with self.assertRaises(AssertionError):verify(d,i)
 def test_missing_automatic_command_and_encoder_paths_are_rejected(self):
  for operation in ['automatic_command_buffer','automatic_compute_encoder','automatic_compute_factories_enabled']:
   d,i=fixture();d['function_events']=[e for e in d['function_events']if e['operation']!=operation]
   with self.assertRaises(AssertionError):verify(d,i)
 def test_wrong_source_and_abi_are_rejected(self):
  d,i=fixture(True);d['function_events'][3]['schema']['members'][0]['type']=60
  with self.assertRaises(AssertionError):verify(d,i)
  d,i=fixture();i['assets_SHA256']['native_producer.metallib']='other'
  with self.assertRaises(AssertionError):verify(d,i)
 def test_imported_pipeline_path_cannot_be_called_native(self):
  for operation in ['IRv2_pipeline_contract_request','new_registered_IRv2_pipeline','register_native_source_IRv2_function']:
   d,i=fixture();d['function_events'].append(dict(operation=operation))
   with self.assertRaises(AssertionError):verify(d,i)
 def test_native_forwarding_is_checked_without_inventing_a_second_callback(self):
  import copy
  d,i=fixture(True,'2:8:5');inner=copy.deepcopy(d['function_events'][2]);inner['selector']='newFunctionWithName:'
  d['function_events'].insert(2,inner);native=copy.deepcopy(next(e for e in d['function_events']if e['operation']=='register_native_IRv2_function'));d['function_events'].insert(3,native)
  next(e for e in d['function_events']if e['operation']=='restore_IRv2_functions')['live_functions_restored']=2
  self.assertEqual(verify(d,i)['native_forwarded_function_calls'],1)
  inner['selector']='unrecognizedInternalSelector:'
  with self.assertRaises(AssertionError):verify(d,i)
 def test_callbacks_and_restoration_are_required(self):
  for field,value in [('function_callbacks',0),('pipeline_callbacks',2),('native_library_restored',False),('native_queue_restored',False)]:
   d,i=fixture(True,'2:8:5');d['library_reception'][field]=value
   with self.assertRaises(AssertionError):verify(d,i)

if __name__=='__main__':unittest.main()
