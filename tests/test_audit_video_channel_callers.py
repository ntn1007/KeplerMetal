# SPDX-License-Identifier: MIT
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'/'tools'))
import audit_video_channel_callers as m
class BranchInventoryTests(unittest.TestCase):
 def test_call_and_tail_jump_are_distinct_and_required(self):
  listing='''  14c5b: e9 46 fc ff ff   jmp 0x148a6 <target>\n  55ba5: e8 fc ec fb ff   callq 0x148a6 <target>\n  55bbb: ff d0 callq *%rax\n'''
  rows=m.parse_direct(listing,{0x148a6,0x14c56});expected=[(0x14c5b,'jmp',0x148a6),(0x55ba5,'call',0x148a6)]
  self.assertEqual(rows,expected);m.verify_direct(rows,expected)
  with self.assertRaises(ValueError):m.verify_direct(rows[1:],expected)
  with self.assertRaises(ValueError):m.verify_direct(rows+rows[:1],expected)
 def test_rel32_destination_and_opcode(self):
  raw=bytes.fromhex('e946fcffff')
  with patch.object(m,'file_bytes',return_value=(0,raw)):
   m.validate_site(b'',0x14c5b,'jmp',0x148a6)
   with self.assertRaises(ValueError):m.validate_site(b'',0x14c5b,'call',0x148a6)
   with self.assertRaises(ValueError):m.validate_site(b'',0x14c5b,'jmp',0x148a7)
if __name__=='__main__':unittest.main()
