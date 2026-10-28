# SPDX-License-Identifier: MIT
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge'/'tools'))
import audit_high_sierra_video as a
class HighSierraAuditTests(unittest.TestCase):
 def factory(self):
  return {'UUID':'x','file_SHA256':'x','slice_SHA256':'x','function_start':0x1e79c,'function_bytes':11,'function_SHA256':'x','exact_known_return_14_stub':True}
 def test_factory_rejects_size_address_and_nonstub(self):
  row=self.factory();a.check_factory('high-sierra',row)
  for key,value in [('function_start',0),('function_bytes',571),('exact_known_return_14_stub',False)]:
   with self.assertRaises(ValueError):a.check_factory('high-sierra',{**row,key:value})
 def test_vtable_requires_exact_inherited_relocation(self):
  sym=[{'name':a.VTABLE,'value':0x8bce8}];base={'symbol':{'name':a.INHERITED},'external':1,'type':0,'length_code':3,'pc_relative':0}
  with patch.object(a,'symbols_and_external_relocations',return_value=(sym,{0x8c638:[base]})),patch.object(a,'file_bytes',return_value=(0,b'\0'*8)):
   a.check_vtable('high-sierra',b'')
  for key,value in [('external',0),('length_code',2),('pc_relative',1)]:
   with patch.object(a,'symbols_and_external_relocations',return_value=(sym,{0x8c638:[{**base,key:value}]})),patch.object(a,'file_bytes',return_value=(0,b'\0'*8)):
    with self.assertRaises(ValueError):a.check_vtable('high-sierra',b'')
if __name__=='__main__':unittest.main()
