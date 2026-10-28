"""CPU-only checks for bounded signed-relative selector-table decoding."""
import struct
import importlib.util
import unittest
from pathlib import Path

spec=importlib.util.spec_from_file_location('kepler_video_gva_dispatch_audit',Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_dispatch/audit.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
decode_table,validate_region=module.decode_table,module.validate_region

class DispatchTable(unittest.TestCase):
    def test_signed_offsets_and_shared_destination(self):
        data=bytearray(256);start=1000;table=128
        for i in range(15):
            destination=start+(10 if i in (0,7) else 200)
            struct.pack_into('<i',data,table+4*i,destination-(start+table))
        result=decode_table(data,start,table,15)
        self.assertEqual([k for k,v in result.items() if v==1010],[2,9])
        self.assertEqual(result[16],1200)

    def test_rejects_truncated_table_and_outside_destination(self):
        data=bytearray(256)
        with self.assertRaises(ValueError):decode_table(data,1000,230,15)
        with self.assertRaises(ValueError):decode_table(data,1000,128,14)
        struct.pack_into('<i',data,128,9999)
        with self.assertRaises(ValueError):decode_table(data,1000,128,15)

    def test_changed_or_unrelated_code_is_not_accepted(self):
        with self.assertRaises(ValueError):validate_region(bytes(719))

if __name__=='__main__':unittest.main()
