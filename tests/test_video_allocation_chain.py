# SPDX-License-Identifier: MIT
"""CPU-only contract tests for static call and vtable validation."""
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
import video_allocation_chain as chain

class AllocationChainValidation(unittest.TestCase):
 def test_direct_call_target_and_opcode(self):
  source,target=0x1000,0x2090
  with patch.object(chain,'at',return_value=b'\xe8'+struct.pack('<i',target-source-5)):
   chain.direct(b'',source,target)
   with self.assertRaises(ValueError):chain.direct(b'',source,target+1)
  with patch.object(chain,'at',return_value=b'\x90\x00\x00\x00\x00'):
   with self.assertRaises(ValueError):chain.direct(b'',source,target)
 def test_internal_slot_requires_target_and_symbol(self):
  symbols=[{'value':0x1234,'name':'exact','type':0x0e}]
  with patch.object(chain,'at',return_value=struct.pack('<Q',0x1234)):
   chain.slot(b'',{},symbols,0x100,0x20,(0x1234,'exact'))
   with self.assertRaises(ValueError):chain.slot(b'',{},symbols,0x100,0x20,(0x1234,'other'))
   with self.assertRaises(ValueError):chain.slot(b'',{0x120:[{}]},symbols,0x100,0x20,(0x1234,'exact'))
 def test_external_slot_requires_zero_and_exact_single_relocation(self):
  relocation={'symbol':{'name':'expected'}}
  with patch.object(chain,'at',return_value=bytes(8)):
   chain.slot(b'',{0x120:[relocation]},[],0x100,0x20,'expected')
   for rel in ({},{0x120:[relocation,relocation]},{0x120:[{'symbol':{'name':'other'}}]}):
    with self.assertRaises(ValueError):chain.slot(b'',rel,[],0x100,0x20,'expected')
  with patch.object(chain,'at',return_value=struct.pack('<Q',1)):
   with self.assertRaises(ValueError):chain.slot(b'',{0x120:[relocation]},[],0x100,0x20,'expected')

if __name__=='__main__':unittest.main()
