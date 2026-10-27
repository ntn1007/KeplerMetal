# SPDX-License-Identifier: MIT
import importlib.util,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('shared_delete_contract',ROOT/'bridge/tools/video_shared_delete_contract.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class SharedDeleteTests(unittest.TestCase):
    def test_unqualified_binaries_rejected_before_parsing(self):
        with tempfile.TemporaryDirectory() as t:
            io=Path(t)/'io';ge=Path(t)/'ge';io.write_bytes(b'not a driver');ge.write_bytes(b'not a driver')
            with self.assertRaisesRegex(ValueError,'Exact binary profile differs'):mod.static_tables(io,ge)
    def test_mutated_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);(root/'0x53284.private.json').write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'REA capture hash differs'):mod.evidence(root,root,root)
if __name__=='__main__':unittest.main()
