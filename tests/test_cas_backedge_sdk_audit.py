# SPDX-License-Identifier: MIT
"""CPU-only tests for per-diagnosis recognizer provenance checks."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
import audit_cas_backedge_sdk as audit

class CASBackedgeSDKProvenance(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);p=Path(self.temp.name);self.overlay=p/'overlay';self.generated=p/'generated';(self.overlay/'tools').mkdir(parents=True);assets=self.generated/'KeplerNativeCAS/assets';assets.mkdir(parents=True)
  self.recognizer=p/'recognizer.py';self.recognizer.write_bytes(b'expected source');h=hashlib.sha256(self.recognizer.read_bytes()).hexdigest();(self.overlay/'tools/recognize_native_cas.py').write_bytes(b'expected source');(self.overlay/'inputs.json').write_text(json.dumps({'source_SHA256':{'tools/recognize_native_cas.py':h}}))
  rows=[{'function':'good','candidate':True},{'function':'control','candidate':False}];(assets/'client-manifest.json').write_text(json.dumps({'profiles':rows}))
  for name,candidate in [('good',True),('control',False)]:
   d=self.generated/('diagnosis-'+name);d.mkdir();(d/'recognize_native_cas.py').write_bytes(b'expected source');state={'candidate':candidate,'AIR':{'qualified':candidate,'expected_output_component':0},'SASS':{'qualified':True}}
   (d/'diagnosis.json').write_text(json.dumps(state));(d/'native.sass').write_bytes(b'code');(d/'native.asm').write_text('listing')
 def runcheck(self):
  with mock.patch.object(audit,'sass_contract',return_value={'qualified':True}):return audit.check_diagnostics(self.generated,self.overlay,self.recognizer)
 def test_matching_sources_and_diagnosis(self):
  digest,proof=self.runcheck();self.assertEqual(len(proof),2);self.assertEqual(proof[0]['recognizer_SHA256'],digest)
 def test_changed_capture_is_refused(self):
  (self.generated/'diagnosis-good/recognize_native_cas.py').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'captured recognizer'):self.runcheck()
 def test_changed_overlay_is_refused(self):
  (self.overlay/'tools/recognize_native_cas.py').write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'overlay recognizer'):self.runcheck()
 def test_current_structural_verdict_must_match(self):
  with mock.patch.object(audit,'sass_contract',return_value={'qualified':False}):
   with self.assertRaisesRegex(ValueError,'structural diagnosis'):audit.check_diagnostics(self.generated,self.overlay,self.recognizer)
 def test_negative_air_must_remain_unqualified(self):
  p=self.generated/'diagnosis-control/diagnosis.json';r=json.loads(p.read_text());r['AIR']['qualified']=True;p.write_text(json.dumps(r))
  with self.assertRaisesRegex(ValueError,'negative AIR'):self.runcheck()

if __name__=='__main__':unittest.main()
