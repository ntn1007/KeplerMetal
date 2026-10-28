# SPDX-License-Identifier: MIT
import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'/'tools'))
import video_selector_path_audit as m
class SelectorPathTests(unittest.TestCase):
 def test_only_qualified_non_special_high_selectors_get_conditional_prediction(self):
  self.assertEqual(m.predict(0x105,True,True,True,True),'CONDITIONAL_UNSUPPORTED')
  self.assertEqual(m.predict(8,True,True,True,True),'CONDITIONAL_UNSUPPORTED')
  self.assertEqual(m.predict(7,True,True,True,True),'UNKNOWN_SUPPORTED_INDEX')
  self.assertEqual(m.predict(6,True,True,True,True),'UNKNOWN_SPECIAL_DISPATCH')
  self.assertEqual(m.predict(0x105,False,True,True,True),'UNKNOWN_OTHER_CLIENT_BRANCH')
  self.assertEqual(m.predict(0x105,True,False,True,True),'CONDITIONAL_NOT_READY')
  self.assertEqual(m.predict(0x105,True,True,False,True),'UNKNOWN_ASYNCHRONOUS')
  self.assertEqual(m.predict(0x105,True,True,True,False),'UNKNOWN_DESCRIPTOR_PATH')
  for value in (-1,2**32,True,'261'):
   self.assertEqual(m.predict(value,True,True,True,True),'REFUSED_INVALID_INPUT')
  self.assertEqual(m.predict(0x105,1,True,True,True),'REFUSED_INVALID_INPUT')
 def test_bad_elf_or_relocation_refused(self):
  for b in (b'',b'\x7fELF\x02\x01'+bytes(58)):
   with self.assertRaises(ValueError):m.elf_text(b)
  with self.assertRaises(ValueError):m.relocation({},0x100,'expected')
  base={'symbol':{'name':'expected'},'external':1,'length_code':3,'type':0,'pc_relative':0}
  m.relocation({0x100:[base]},0x100,'expected')
  for key,value in [('external',0),('length_code',2),('pc_relative',1)]:
   with self.assertRaises(ValueError):m.relocation({0x100:[{**base,key:value}]},0x100,'expected')
 def test_omitted_or_changed_instruction_is_rejected(self):
  expected={0x10:r'cmp edx, 0x7',0x20:r'xor eax, eax'}
  m.check_rows({0x10:'cmp edx, 0x7',0x20:'xor eax, eax'},expected)
  with self.assertRaises(ValueError):m.check_rows({0x10:'cmp edx, 0x7'},expected)
  with self.assertRaises(ValueError):m.check_rows({0x10:'cmp edx, 0x8',0x20:'xor eax, eax'},expected)
if __name__=='__main__':unittest.main()
