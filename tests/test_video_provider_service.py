# SPDX-License-Identifier: MIT
import copy
import importlib.util
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('provider_service_audit', ROOT/'bridge/experiments/video_provider_service/audit.py')
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
            'sierra_loaded':False,'sierra_export_called':False,'gate_return':14,'gate_calls':1,'argument_observation':obs,
            'events':[{'name':'AVD_CreateAVDAccelerator','identity_pin':True,'result_replaced':True}]}

class ServiceAuditTests(unittest.TestCase):
    def test_identity_and_calibration_fail_closed(self):
        original=valid_gate();m.check_gate(original,'enabled')
        for key,value in [('selected_service_registry_ID',m.GPU_ID+1),('selected_service_class','IORegistryEntry'),
                          ('selected_port_send_right',False),('selected_service_registry_ok',False),('display_mask',1)]:
            changed=copy.deepcopy(original);changed['argument_observation'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):m.check_gate(changed,'enabled')
        changed=copy.deepcopy(original);changed['service_calibration_pass']=False
        with self.assertRaises(ValueError):m.check_gate(changed,'enabled')
    def test_negative_path_rejects_gate_call(self):
        gate=valid_gate();gate['gate_calls']=0;gate['argument_observation']['ready']=False
        m.check_gate(gate,'wrong-name');gate['gate_calls']=1
        with self.assertRaises(ValueError):m.check_gate(gate,'wrong-name')

if __name__=='__main__':unittest.main()
