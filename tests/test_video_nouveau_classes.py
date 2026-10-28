# SPDX-License-Identifier: MIT
import importlib.util,struct,sys,unittest
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'bridge/tools'))
spec=importlib.util.spec_from_file_location('video_nouveau_classes',root/'bridge/tools/audit_video_nouveau_classes.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)

class NouveauClassAuditTests(unittest.TestCase):
 def test_registry_ambiguous_and_rejects_changed_input(self):
  s='+-o nvAccelerator  <class nvAccelerator, id 0x100000460, registered>\n"IOVARendererID" = <08000401>\n"IOVARendererSubID" = <03000000>\n'
  r=a.parse_registry(s);self.assertEqual(r['renderer_sub_id'],3);self.assertTrue(r['matches_both_on_disk_class_branches']);self.assertFalse(r['runtime_branch_observed'])
  for bad in [s.replace('03000000','02000000'),s.replace('0x100000460','0x100000461'),s+s,s.replace('08000401','080004')]:
   with self.assertRaises(ValueError):a.parse_registry(bad)
 def test_anchors_reject_missing_and_duplicate(self):
  a.check_fragments('alpha beta',['alpha','beta'])
  for value in ['alpha','alpha beta beta']:
   with self.assertRaises(ValueError):a.check_fragments(value,['alpha','beta'])
 def test_instruction_and_jump_mutations_are_rejected(self):
  targets=[0x3e97d,0x3e9f8,0x3e989,0x3e995,0x3e9f8,0x3e9f8,0x3e9f8,0x3e9a1]
  entries={k:bytes.fromhex(v) for k,v in a.SITES.items()};entries[0x3ea08]=struct.pack('<8i',*[x-0x3ea08 for x in targets])
  def read(_data,addr,length):return addr,entries[addr][:length]
  with patch.object(a,'file_bytes',side_effect=read):
   a.verify_instructions(b'');old=entries[0x9ae5];entries[0x9ae5]=b'\x90'+old[1:]
   with self.assertRaises(ValueError):a.verify_instructions(b'')
   entries[0x9ae5]=old;entries[0x3ea08]=struct.pack('<8i',*[x-0x3ea08 for x in targets[::-1]])
   with self.assertRaises(ValueError):a.verify_instructions(b'')

if __name__=='__main__':unittest.main()
