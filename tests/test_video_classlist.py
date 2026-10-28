# SPDX-License-Identifier: MIT
import importlib.util,struct,unittest
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]/'bridge/experiments/video_classlist'
def module(name):
 spec=importlib.util.spec_from_file_location('classlist_'+name,root/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
o=module('offline');a=module('audit')

class ClassListTests(unittest.TestCase):
 def data(self,*values):return struct.pack('<'+str(len(values))+'I',*values)
 def test_selection_uses_candidate_priority_not_list_order(self):
  x=o.classify(self.data(0x90b1,0x90b2,0x90b3,0x95b2,0x95b1),5)
  self.assertEqual(x['candidate_selection'],{'BSP':'0x95b1','VP':'0x95b2','PPP':'0x90b3'});self.assertFalse(x['actual_classlist_attested']);self.assertFalse(x['GPU_or_driver_query_performed'])
  y=o.classify(self.data(0x90b1,0x90b2),2);self.assertEqual(y['candidate_selection'],{'BSP':'0x90b1','VP':'0x90b2','PPP':None})
  self.assertEqual(o.classify(b'',0)['candidate_selection'],{'BSP':None,'VP':None,'PPP':None})
 def test_malformed_count_length_and_type_rejected(self):
  for data,count in [(b'',1),(b'abc',1),(b'\0'*8,1),(b'',-1),(b'',True),(b'',o.MAX_CLASSES+1)]:
   with self.assertRaises(ValueError):o.classify(data,count)
 def test_vendor_declaration_does_not_accept_changed_command_or_layout(self):
  s='#define NV0080_CTRL_CMD_GPU_GET_CLASSLIST (0x800201)\ntypedef struct NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS { NvU32 numClasses; NV_DECLARE_ALIGNED(NvP64 classList, 8); } NV0080_CTRL_GPU_GET_CLASSLIST_PARAMS;'
  self.assertIn('numClasses',a.declaration(s))
  for bad in (s.replace('0x800201','0x800202'),s.replace('classList, 8','classList, 4'),s+'\n'+s):
   with self.assertRaises(ValueError):a.declaration(bad)
 def test_static_instruction_and_branch_mutations_rejected(self):
  entries={k:bytes.fromhex(v) for k,v in a.SITES.items()}
  for site,target in [(0x9568,0xc842),(0x9588,0xca6e)]:entries[site]=b'\xe8'+struct.pack('<i',target-site-5)
  def fake(_data,addr,length):return addr,entries[addr][:length]
  with patch.object(a,'file_bytes',side_effect=fake):
   a.check_sites(b'');old=entries[0xc886];entries[0xc886]=b'\xba\x02'+old[2:]
   with self.assertRaises(ValueError):a.check_sites(b'')
   entries[0xc886]=old;entries[0x9568]=b'\xe8\0\0\0\0'
   with self.assertRaises(ValueError):a.check_sites(b'')

if __name__=='__main__':unittest.main()
