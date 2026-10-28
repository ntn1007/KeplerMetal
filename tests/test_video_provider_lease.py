# SPDX-License-Identifier: MIT
import copy
import importlib.util
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('provider_lease_audit', ROOT/'bridge/experiments/video_provider_lease/audit.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def valid_gate():
    keys=('caller_pinned','caller_path_matches','caller_UUID_matches','config_header_20_read',
          'display_array_region_readable','selected_index_in_mask','selected_index_in_range',
          'selected_display_value_nonzero','selected_port_send_right','selected_service_class_ok',
          'selected_service_registry_ok','region_is_not_allocation_size_proof')
    obs = {key: True for key in keys}
    obs.update(ready=True,caller_offset=0x24d16,config_first_word=0,display_mask=15,
               display_array_required_count=4,selected_service_class='nvAccelerator',selected_service_registry_ID=m.GPU_ID)
    return {'status':'COMPLETE','calibration_pass':True,'service_calibration_pass':True,'drained':True,'dropped':0,
            'failure_output_unowned':False,'association_probe_enabled':True,'metal_registry_matches':True,'shared_open_attempts':1,'shared_open_status':0,'shared_close_attempts':1,'shared_close_status':0,'connections_distinct':True,'association_attempts':1,'association_status':0,'context_probe_enabled':True,'context_open_attempts':1,'context_open_status':0,'context_close_attempts':1,'context_close_status':0,'explicit_video_external_methods':0,'explicit_gpu_dispatches_by_gate':0,'sierra_loaded':False,'sierra_export_called':False,'gate_return':14,'gate_calls':1,'argument_observation':obs,
            'events':[{'name':'AVD_CreateAVDAccelerator','identity_pin':True,'result_replaced':True}]}

class LeaseAuditTests(unittest.TestCase):
    def test_identity_and_calibration_fail_closed(self):
        original=valid_gate();m.check_gate(original,'enabled',True,True)
        for key,value in [('selected_service_registry_ID',m.GPU_ID+1),('selected_service_class','IORegistryEntry'),
                          ('selected_port_send_right',False),('selected_service_registry_ok',False),('display_mask',1)]:
            changed=copy.deepcopy(original);changed['argument_observation'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):m.check_gate(changed,'enabled',True,True)
        changed=copy.deepcopy(original);changed['failure_output_unowned']=True
        with self.assertRaises(ValueError):m.check_gate(changed,'enabled',True,True)
        changed=copy.deepcopy(original);changed['association_status']=1
        with self.assertRaises(ValueError):m.check_gate(changed,'enabled',True,True)
        changed=copy.deepcopy(original);changed['context_close_status']=1
        with self.assertRaises(ValueError):m.check_gate(changed,'enabled',True,True)
        changed=copy.deepcopy(original);changed['service_calibration_pass']=False
        with self.assertRaises(ValueError):m.check_gate(changed,'enabled',True,True)
    def test_negative_path_rejects_gate_call(self):
        gate=valid_gate();gate['gate_calls']=0;gate['argument_observation']['ready']=False;gate.update(context_probe_enabled=False,context_open_attempts=0,context_close_attempts=0,context_open_status=-2147483648,context_close_status=-2147483648,association_probe_enabled=False,shared_open_attempts=0,shared_close_attempts=0,association_attempts=0,shared_open_status=-2147483648,shared_close_status=-2147483648,association_status=-2147483648)
        m.check_gate(gate,'wrong-name',False,False);gate['gate_calls']=1
        with self.assertRaises(ValueError):m.check_gate(gate,'wrong-name',False,False)

if __name__=='__main__':unittest.main()
