# SPDX-License-Identifier: MIT
import importlib.util, json, struct, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('video_gva_selection_static',ROOT/'bridge/tools/video_gva_selection_static.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class RelativeTests(unittest.TestCase):
 def test_forward_and_backward(self):
  self.assertEqual(mod.relative(b'\xe8'+struct.pack('<i',42),100,100,b'\xe8'),147)
  self.assertEqual(mod.relative(b'\x0f\x84'+struct.pack('<i',-20),200,200,b'\x0f\x84'),186)
 def test_reject_truncated_wrong_opcode_and_negative_offset(self):
  for b,start,site,opcode in [(b'\xe8\x00',0,0,b'\xe8'),(b'\x90'*5,0,0,b'\xe8'),(b'\xe8'+bytes(4),2,1,b'\xe8')]:
   with self.subTest(b=b,start=start,site=site),self.assertRaises(ValueError):mod.relative(b,start,site,opcode)
class StubMapTests(unittest.TestCase):
 def test_static_target_must_match_and_not_claim_runtime(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'map.json';data={'status':'STATIC_ONLY','source_region_SHA256':'region','runtime_target_proved':False,'rows':[{'caller_offset':4,'exact_defined_symbols':['symbol'],'runtime_target_proved':False}]};p.write_text(json.dumps(data));h=mod.digest(p.read_bytes());mod.mapped(p,h,'region',[(4,'symbol')])
   with self.assertRaises(ValueError):mod.mapped(p,h,'region',[(4,'wrong')])
   data['rows'][0]['runtime_target_proved']=True;p.write_text(json.dumps(data))
   with self.assertRaises(ValueError):mod.mapped(p,mod.digest(p.read_bytes()),'region',[(4,'symbol')])
   with self.assertRaises(ValueError):mod.mapped(p,h,'region',[(4,'symbol')])
if __name__=='__main__':unittest.main()
