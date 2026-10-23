"""Independent receipt controls for the public native-function binding path."""
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_command_ir_dataflow import verify_native_function_arguments

class NativeFunctionArgumentReceipts(unittest.TestCase):
    def fixture(self,reuse=False):
        schema=dict(buffer_index=0,binding_count=4,encoded_length=48,alignment=8,
            members=[dict(type=t,offset=i*8,index=i)for i,t in enumerate([60,85,60,60,60,60])])
        registration=dict(operation='register_native_source_IRv2_function',library_SHA256='digest',
            function='encode_dataflow_basic',instruction_import=False,native_pipeline_factories_preserved=True,
            Apple_ICB_identity=False,GPU_execution=False,schema=schema)
        getters=[dict(operation='function_IRv2_argument_encoder',reflection_requested=False)]
        for i in range(1 if reuse else 4):
            getters.append(dict(operation='function_IRv2_argument_encoder',reflection_requested=bool(i%2),native_reflection_preserved=bool(i%2)))
        events=[registration,*getters,dict(operation='restore_IRv2_functions',live_functions_restored=1)]
        data=dict(producer_backend='native_msl',public_argument_encoder=True,function_argument_encoder=True,
            argument_refusal_probe=False,mode='encoder_reuse'if reuse else'basic',function_events=events,
            producer_info=dict(function='encode_dataflow_basic'),runs=[dict(events=[dict(operation='encode_public_IRv2_arguments',native_Apple_ICB_identity=False,bytes=48)for _ in range(4)])for _ in range(4)])
        return data,dict(native_function_arguments=True,assets_SHA256={'native_producer.metallib':'digest'})

    def test_each_stride_and_trial_getter_is_accounted_for(self):
        for reuse in [False,True]:verify_native_function_arguments(*self.fixture(reuse))

    def test_missing_getter_or_reflection_cannot_claim_complete_binding(self):
        for reuse in [False,True]:
            data,inputs=self.fixture(reuse);data['function_events'].pop(1)
            with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)
        data,inputs=self.fixture();data['function_events'][3]['native_reflection_preserved']=False
        with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)

    def test_wrong_wire_abi_and_wrong_library_are_rejected(self):
        for key,value in [('binding_count',3),('encoded_length',40),('alignment',16),('buffer_index',1)]:
            data,inputs=self.fixture();data['function_events'][0]['schema'][key]=value
            with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)
        for index in range(6):
            data,inputs=self.fixture();data['function_events'][0]['schema']['members'][index]['type']^=1
            with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)
        data,inputs=self.fixture();inputs['assets_SHA256']['native_producer.metallib']='different'
        with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)

    def test_restoration_and_no_instruction_import_are_required(self):
        for field,value in [('instruction_import',True),('native_pipeline_factories_preserved',False),('Apple_ICB_identity',True),('GPU_execution',True)]:
            data,inputs=self.fixture();data['function_events'][0][field]=value
            with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)
        data,inputs=self.fixture();data['function_events'][-1]['live_functions_restored']=0
        with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)

    def test_unowned_or_missing_root_is_rejected(self):
        for field,value in [('native_Apple_ICB_identity',True),('bytes',40)]:
            data,inputs=self.fixture();data['runs'][2]['events'][1][field]=value
            with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)
        data,inputs=self.fixture();data['runs'][0]['events'].pop()
        with self.assertRaises(AssertionError):verify_native_function_arguments(data,inputs)

if __name__=='__main__':unittest.main()
