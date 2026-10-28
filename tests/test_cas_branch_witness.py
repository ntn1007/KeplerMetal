"""CPU-only counterexamples for branch-register witness results."""
import copy
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/experiments/cas_divergence'))
from verify_branch_witness import compare,verify_baseline

def fixture(pattern):
    report={'status':'COMPLETED','device':'NVIDIA GeForce GTX 880M','registry_id':4294968416,
            'GPU_dispatch':True,'command_status':4,'mode':'baseline','pattern':pattern,
            'threads':33,'groups':3,'variant':1,'seed':0x1234}
    b=bytearray(b'\xa5'*1712);t=bytearray(b'\xa5'*1712);marker={0:1,2:0x98,3:0xb8,4:0x30}[pattern]
    for i in range(99):
        group,tid=divmod(i,33);initial=0x1234+group*0x10001+tid*13
        active=pattern==2 and tid%2==0 or pattern==3 and tid<17
        row=(initial^1,0,initial,i^0x6d2b79f5^(0x80000000 if active else 0))
        struct.pack_into('<4I',b,64+i*16,*row);struct.pack_into('<4I',t,64+i*16,row[0],marker,row[2],row[3])
    tr=dict(report,mode='trace');return bytes(b),report,bytes(t),tr

class BranchWitness(unittest.TestCase):
    def test_expected_markers(self):
        for pattern,marker in ((0,1),(2,0x98),(3,0xb8),(4,0x30)):
            result=compare(*fixture(pattern))
            self.assertEqual(result['markers'],{str(marker):99})
            self.assertFalse(result['all_paths_qualified'])

    def test_guard_and_non_witness_mutations_rejected(self):
        for offset in (0,64,72,76):
            b,br,t,tr=fixture(2);t=bytearray(t);t[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):compare(b,br,bytes(t),tr)

    def test_unexpected_or_control_marker_rejected(self):
        b,br,t,tr=fixture(2);t=bytearray(t);struct.pack_into('<I',t,68,17)
        with self.assertRaisesRegex(ValueError,'unexpected marker'):compare(b,br,bytes(t),tr)
        b,br,t,tr=fixture(0);t=bytearray(t);struct.pack_into('<I',t,68,0x98)
        with self.assertRaisesRegex(ValueError,'inactive control'):compare(b,br,bytes(t),tr)

    def test_baseline_mutation_and_pattern_mismatch_rejected(self):
        b,br,t,tr=fixture(3);bad=bytearray(b);bad[64]^=1
        with self.assertRaises(ValueError):verify_baseline(bytes(bad),br)
        tr=copy.deepcopy(tr);tr['pattern']=2
        with self.assertRaises(ValueError):compare(b,br,t,tr)

if __name__=='__main__':unittest.main()
