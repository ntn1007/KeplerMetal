# SPDX-License-Identifier: MIT
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
import video_resource_ownership as audit

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'capture.json'
        self.address = '0x1234'
        self.evidence = {'operation':'analyze_function', 'subject':{'digest':{'sha256':audit.IO_SHA}},
                         'evidence_id':'ev-test', 'provider':{'id':'ghidra','name':'Ghidra','version':'12.1.4'},
                         'analysis_profile':{'digest':'c027fac311b23874c52441ed55610273dff33987b0370a0589c90be8f6d72b7a'},
                         'normalized_result':{'procedure':{'address':self.address,'body':{'total_bytes':2}},
                                              'assembly':['0x1234: RET']}}

    def write(self):
        raw=json.dumps({'result':{'structuredContent':self.evidence}}).encode()
        self.path.write_bytes(raw)
        return ('link', hashlib.sha256(raw).hexdigest(), 'ev-test', 2, ['0x1234: RET'])

    def test_valid_capture_and_modified_bytes_rejected(self):
        spec=self.write()
        self.assertEqual(audit.check_evidence(self.path,self.address,spec)['evidence_id'],'ev-test')
        self.path.write_bytes(self.path.read_bytes()+b' ')
        with self.assertRaisesRegex(ValueError,'hash differs'):
            audit.check_evidence(self.path,self.address,spec)

    def test_consistently_rehashed_wrong_subject_and_missing_instruction_rejected(self):
        self.evidence['subject']['digest']['sha256']='0'*64
        spec=self.write()
        with self.assertRaisesRegex(ValueError,'identity or instruction'):
            audit.check_evidence(self.path,self.address,spec)
        self.evidence['subject']['digest']['sha256']=audit.IO_SHA
        self.evidence['normalized_result']['assembly']=[]
        spec=self.write()
        with self.assertRaisesRegex(ValueError,'identity or instruction'):
            audit.check_evidence(self.path,self.address,spec)

    def test_unqualified_binary_profile_rejected_before_parsing(self):
        one=Path(self.temp.name)/'io'; two=Path(self.temp.name)/'ge'
        one.write_bytes(b'not the installed driver'); two.write_bytes(b'not the installed driver')
        with self.assertRaisesRegex(ValueError,'profile differs'):
            audit.check_profile(one,two)

if __name__=='__main__':
    unittest.main()
