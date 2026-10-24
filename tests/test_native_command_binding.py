"""Offline malformed QMD controls; no command bytes are submitted to Metal."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_native_command_binding import decode_qmd
from audit_native_command_binding import relative_call


def stream():
    q=bytearray(256)
    for at,value in [(0x20,0x1fe000),(0x30,1),(0x34,0x10001),(0x48,0x10006),(0x4c,0x10001),(0xb8,4<<24)]:
        struct.pack_into('<I',q,at,value)
    return bytearray(struct.pack('<I',(3<<29)|(64<<16)|(1<<13)|(0x1b4//4))+q)


class NativeCommandBinding(unittest.TestCase):
    def bad(self,data):
        with self.assertRaises(AssertionError):decode_qmd(data)

    def test_geometry_and_address(self):
        d=decode_qmd(stream());self.assertEqual(d['program_offset'],0x1fe000)
        self.assertEqual(d['groups'],[1,1,1]);self.assertEqual(d['local'],[1,1,1]);self.assertEqual(d['registers'],4)

    def test_truncated_word(self):self.bad(stream()[:-1])
    def test_truncated_payload(self):self.bad(stream()[:-4])
    def test_duplicate_QMD(self):self.bad(stream()+stream())
    def test_wrong_channel(self):
        data=stream();word=struct.unpack_from('<I',data)[0];struct.pack_into('<I',data,0,word^(1<<13));self.bad(data)

    def test_unknown_mode(self):
        data=stream();word=struct.unpack_from('<I',data)[0];struct.pack_into('<I',data,0,(word&0x1fffffff)|(2<<29));self.bad(data)

    def test_zero_payload_count(self):
        data=stream();word=struct.unpack_from('<I',data)[0];struct.pack_into('<I',data,0,word&~(0x1fff<<16));self.bad(data)

    def test_payload_count_overflow(self):
        data=stream();word=struct.unpack_from('<I',data)[0];struct.pack_into('<I',data,0,(word&~(0x1fff<<16))|(0x1fff<<16));self.bad(data)

    def test_no_QMD(self):self.bad(struct.pack('<2I',(1<<29)|(1<<16)|(1<<13)|0x40,0))
    def test_wrong_version(self):
        data=stream();struct.pack_into('<I',data,4+0x48,0x10007);self.bad(data)

    def test_wrong_geometry(self):
        data=stream();struct.pack_into('<I',data,4+0x30,2);self.bad(data)

    def test_inline_packet_has_no_payload(self):
        inline=struct.pack('<I',(4<<29)|(17<<16)|(1<<13)|(0x1b0//4))
        self.assertEqual(decode_qmd(inline+stream())['packet_count'],2)

    def test_captured_relative_call_targets_entry(self):
        self.assertEqual(relative_call(0x5003ffffc0011c07,8),dict(PC=8,displacement=-16,target=0,kind='PC_relative_CALL'))

    def test_call_target_is_relative_not_absolute_GPU_zero(self):
        self.assertEqual(relative_call(0x5003ffffc0011c07,0x108)['target'],0x100)

    def test_forward_call_and_zero_displacement(self):
        self.assertEqual(relative_call(0x5000000000000007|(32<<26),8)['target'],48)
        self.assertEqual(relative_call(0x5000000000000007,8)['target'],16)

    def test_non_call_and_constant_call_variant_not_accepted(self):
        self.assertIsNone(relative_call(0,8))
        self.assertIsNone(relative_call(0x5000000000004007,8))


if __name__=='__main__':unittest.main()
