# SPDX-License-Identifier: MIT
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from video_reply_bounds import checked_reply

class VideoReplyBounds(unittest.TestCase):
    def test_complete_49_byte_reply(self):
        header, tail = checked_reply(0,49,49,1,bytes(range(49)))
        self.assertEqual(header,bytes(range(48)))
        self.assertEqual(tail,b'\x30')

    def test_header_only_profile(self):
        self.assertEqual(checked_reply(0,48,48,0,b'a'*48),(b'a'*48,b''))

    def test_refuses_short_or_inconsistent_results(self):
        for returned in (0,47,48,50):
            with self.subTest(returned=returned), self.assertRaises(ValueError):
                checked_reply(0,49,returned,1,b'x'*49)
        with self.assertRaises(ValueError): checked_reply(0,49,49,1,b'x'*48)
        with self.assertRaises(ValueError): checked_reply(1,49,49,1,b'x'*49)
        with self.assertRaises(ValueError): checked_reply(0,48,48,1,b'x'*48)

    def test_types_and_limits(self):
        for args in [(0,49,49,True,b'x'*49),(0,49,49,-1,b'x'*49),(0,4097,4097,4049,b'x'*4097),(0,49,49,1,'x'*49)]:
            with self.subTest(args=args[:4]), self.assertRaises(ValueError): checked_reply(*args)
        with self.assertRaises(ValueError): checked_reply(0,49,49,1,memoryview(b'x'*98)[::2])

if __name__=='__main__': unittest.main()
