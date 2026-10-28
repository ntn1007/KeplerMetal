"""CPU-only counterexamples for the bounded CB0 readback oracle."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/experiments/cas_divergence'))
from verify_cb0_readback import verify

def fixture(mode='cb0'):
    report={'status':'COMPLETED','device':'NVIDIA GeForce GTX 880M','registry_id':4294968416,
            'GPU_dispatch':True,'command_status':4,'threads':33,'groups':3,'pattern':0,'variant':1,
            'seed':0x1234,'mode':mode}
    values=[0x298,0x2b8,0x330] if mode=='cb0' else [0x111,0x222,0x333]
    output=bytearray(b'\xa5'*(128+99*16))
    for i in range(99):struct.pack_into('<4I',output,64+i*16,*values,i^0x6d2b79f5)
    return report,output

class CB0ReadbackOracle(unittest.TestCase):
    def test_control_and_matching_table(self):
        for mode in ('control','cb0'):
            report,output=fixture(mode);r=verify(bytes(output),report)
            self.assertEqual(r['status'],'PASS');self.assertEqual(r['rows'],99)
    def test_uniform_different_table_is_observation_not_pass(self):
        report,output=fixture()
        for i in range(99):struct.pack_into('<I',output,64+i*16,17)
        r=verify(bytes(output),report);self.assertEqual(r['status'],'OBSERVED_DIFFERENT')
        self.assertFalse(r['candidate_section_matches'])
    def test_bad_guards_witness_or_nonuniform_values_fail(self):
        for offset in (0,64,64+12):
            report,output=fixture();output[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):verify(bytes(output),report)
    def test_bad_control_profile_and_truncated_output_fail(self):
        report,output=fixture('control');output[64]^=1
        with self.assertRaises(ValueError):verify(bytes(output),report)
        report,output=fixture();report['command_status']=3
        with self.assertRaises(ValueError):verify(bytes(output),report)
        report,output=fixture()
        with self.assertRaises(ValueError):verify(bytes(output[:-1]),report)

if __name__=='__main__':unittest.main()
