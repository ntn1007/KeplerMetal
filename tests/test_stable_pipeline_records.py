"""Wire-oracle edge cases; hardware reception remains independently required."""
from pathlib import Path
import struct,sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_stable_pipeline_records import expected,ERROR,MAGIC
ADDRESS=0x500001040

def words(op,row=0):return struct.unpack_from('<32I',expected(op,ADDRESS),128+row*128)

class StablePipelineWireOracle(unittest.TestCase):
    def test_candidate_position_depends_on_template_requirements(self):
        self.assertEqual(words(0)[2],0)
        self.assertEqual(words(1)[2],2)
        self.assertEqual(words(2)[2],3)
        self.assertEqual(words(6)[2],1)
        self.assertEqual(words(13)[2],0)
        self.assertEqual(words(14)[2],3)
        self.assertEqual(words(14)[18],16)
        self.assertEqual(words(20)[2],3)
        self.assertEqual(words(20)[18],0)

    def test_setter_order_preserves_the_same_final_command(self):
        self.assertEqual(expected(1,ADDRESS),expected(4,ADDRESS))
        self.assertEqual(expected(1,ADDRESS),expected(5,ADDRESS))
        self.assertEqual(words(3)[4:11],(16,1,1,1,16,1,1))
        self.assertEqual(words(1)[16]|words(1)[17]<<32,ADDRESS+128)

    def test_stale_identity_and_count_refusals_preserve_error_semantics(self):
        for op in [7,8,15,16]:
            self.assertEqual(words(op)[1],ERROR)
            self.assertEqual(words(op)[2:4],(0,0))
            self.assertEqual(words(op)[19],1)
        self.assertEqual(words(9)[1],ERROR|1)
        self.assertEqual(words(9)[3],0x4b504950)

    def test_copy_reset_and_no_dispatch_are_distinct(self):
        self.assertEqual(expected(12,ADDRESS)[128:256],struct.pack('<I',MAGIC)+bytes(124))
        self.assertEqual(words(12,1),words(1))
        for op in range(21):self.assertEqual(expected(op,ADDRESS,False),b'\xa5'*512)
        for op in [10,11]:self.assertEqual(expected(op,ADDRESS),b'\xa5'*512)

    def test_partial_or_nonuniform_commands_are_not_silently_completed(self):
        self.assertEqual(words(17)[1],3)
        self.assertEqual(words(17)[16:18],(0,0))
        self.assertEqual(words(18)[16]|words(18)[17]<<32,ADDRESS+4)
        self.assertEqual(words(19)[4:11],(33,1,1,1,32,1,1))

if __name__=='__main__':unittest.main()
