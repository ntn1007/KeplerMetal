# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import struct
import unittest

MODULE=Path(__file__).resolve().parents[1]/'tools/resident_overlap_contract.py'
SPEC=importlib.util.spec_from_file_location('resident_contract',MODULE)
CONTRACT=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(CONTRACT)

class ResidentStreamContract(unittest.TestCase):
    def setUp(self):
        self.addresses=[0x120000,0x130000]
        self.original=b''.join(CONTRACT.record_tail(a) for a in self.addresses)
        data=bytearray(self.original);struct.pack_into('<I',data,16,0x20012040);self.candidate=bytes(data)
    def test_original_serial_and_bounded_candidate(self):
        CONTRACT.verify_stream(self.original,self.original,self.addresses,False)
        CONTRACT.verify_stream(self.original,self.candidate,self.addresses,True)
    def test_terminal_wait_cannot_be_removed(self):
        data=bytearray(self.candidate);struct.pack_into('<I',data,40,0x20012040)
        with self.assertRaises(ValueError):CONTRACT.verify_stream(self.original,bytes(data),self.addresses,True)
    def test_descriptor_cannot_change(self):
        data=bytearray(self.candidate);struct.pack_into('<I',data,4,0x9876)
        with self.assertRaises(ValueError):CONTRACT.verify_stream(self.original,bytes(data),self.addresses,True)
    def test_shared_descriptor_is_refused(self):
        with self.assertRaises(ValueError):CONTRACT.verify_stream(self.original,self.candidate,[self.addresses[0]]*2,True)
    def test_single_record_cannot_use_two_record_candidate(self):
        original=CONTRACT.record_tail(self.addresses[0])
        with self.assertRaises(ValueError):CONTRACT.verify_stream(original,original,[self.addresses[0]],True)
    def test_missing_change_is_not_silently_qualified(self):
        with self.assertRaises(ValueError):CONTRACT.verify_stream(self.original,self.original,self.addresses,True)
    def test_alignment_and_width(self):
        for address in [0,0x120001,1<<40]:
            with self.assertRaises(ValueError):CONTRACT.record_tail(address)
    def test_truncated_candidate(self):
        with self.assertRaises(ValueError):CONTRACT.verify_stream(self.original,self.candidate[:-1],self.addresses,True)

if __name__=='__main__':unittest.main()
