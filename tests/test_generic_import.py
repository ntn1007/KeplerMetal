"""Portable negative controls for raw-output oracles; no Metal/GPU execution."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import struct
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'bridge/tools'
sys.path.insert(0,str(TOOLS))
from public_generic_import import check_assets
spec = importlib.util.spec_from_file_location('generic_oracle',TOOLS / 'verify_generic_import.py')
oracle = importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
NAME = 'NVIDIA GeForce GTX 880M'
IDENTITY = dict(device=NAME,registry_id=1,device_identity=dict(schema=1,name=NAME,
    registry_id=1,PCI_registry_id=2,PCI_vendor_id=0x10de,PCI_device_id=0x1198))


class GenericOracleTests(unittest.TestCase):
    def test_fixture_hash_and_basename_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'program';p.write_bytes(b'CPU-only fixture, never sent to GPU')
            digest=hashlib.sha256(p.read_bytes()).hexdigest();check_assets(root,{'program':digest})
            for pins in [{'program':'0'*64},{'../program':digest}]:
                with self.assertRaises(AssertionError):check_assets(root,pins)
            with self.assertRaises(FileNotFoundError):check_assets(root,{'missing':digest})

    def tess_fixture(self, root):
        prefix = root / 'capture'; coords = [1.,0.,0.,1.,0.,1.,0.,1.,0.,0.,1.,1.]
        values = [v*v*.5+.125 if i%4 != 3 else 1. for i,v in enumerate(coords)]
        event = dict(stage=2,code_replaced=True,imported_code_identical=True,original_graphics_header_preserved=True)
        r = dict(copy.deepcopy(IDENTITY),command_status=4,mismatches=0,guard_mismatches=0,
            tail_mismatches=0,invocations=3,factor=1,NAK_imported=True,
            **{'import':dict(contract_verified=True,constructor_restored=True,events=[event])})
        guard = bytes([0xa5])*64
        for i,data in enumerate([struct.pack('<I',3),struct.pack('<12f',*coords),struct.pack('<12f',*values)]):
            size = 4 if i == 0 else 32768*16
            Path(str(prefix)+f'.buffer-{i}.bin').write_bytes(guard+data+bytes([0xa5])*(size-len(data))+guard)
        Path(str(prefix)+'.coords.bin').write_bytes(struct.pack('<12f',*coords))
        Path(str(prefix)+'.values.bin').write_bytes(struct.pack('<12f',*values))
        return r,prefix

    def test_tess_raw_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p = self.tess_fixture(Path(tmp)); self.assertEqual(oracle.verify_tess(r,p)['invocations'],3)

    def test_tess_wrong_result_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p = self.tess_fixture(Path(tmp)); f=Path(str(p)+'.values.bin')
            data=bytearray(f.read_bytes());data[:4]=struct.pack('<f',.25);f.write_bytes(data)
            with self.assertRaises(AssertionError): oracle.verify_tess(r,p)

    def test_tess_overwritten_tail_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p = self.tess_fixture(Path(tmp)); f=Path(str(p)+'.buffer-1.bin')
            data=bytearray(f.read_bytes());data[64+48]=0;f.write_bytes(data)
            with self.assertRaises(AssertionError): oracle.verify_tess(r,p)

    def test_tess_unrestored_constructor_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r,p = self.tess_fixture(Path(tmp));r['import']['constructor_restored']=False
            with self.assertRaises(AssertionError): oracle.verify_tess(r,p)

    def test_vertex_missing_draw_and_nan_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'capture'; image=Path(str(p)+'.image.bin')
            r=dict(copy.deepcopy(IDENTITY),command_status=4,mismatched_channels=0,argument_mismatches=0,
                changed_argument_guards=0,mode='native',draw='direct',interpolation='smooth')
            image.write_bytes(bytes(64*48*16))
            with self.assertRaises(AssertionError):oracle.verify_vertex(r,p)
            values=oracle.vertex_reference('direct','native','smooth');image.write_bytes(struct.pack('<12288f',*values))
            self.assertEqual(oracle.verify_vertex(r,p)['float32_channels'],12288)
            values[100]=float('nan');image.write_bytes(struct.pack('<12288f',*values))
            with self.assertRaises(AssertionError):oracle.verify_vertex(r,p)

    def test_native_and_imported_reference_differ(self):
        for interpolation in ['smooth','linear','flat']:
            native=oracle.vertex_reference('direct','native',interpolation)
            for mode in ['vertex','fragment','both']:
                self.assertTrue(any(abs(a-b)>1e-3 for a,b in zip(native,oracle.vertex_reference('direct',mode,interpolation))))
        self.assertTrue(all(v==0 for v in oracle.vertex_reference('indirect-control','both','smooth')))

    def test_wrong_pci_device_rejected(self):
        r=copy.deepcopy(IDENTITY);r['device_identity']['PCI_device_id']=0x0e0a
        with self.assertRaises(AssertionError):oracle.verify_device_identity(r)

    def contract_fixture(self):
        def proof(stages):return dict(contract_verified=True,constructor_restored=True,events=[
            dict(stage=s,code_replaced=True,imported_code_identical=True,original_graphics_header_preserved=True) for s in stages])
        return dict(copy.deepcopy(IDENTITY),status='PASS',GPU_dispatches=0,outer_pipeline_created=True,
            constructor_restored_after_join=True,outer_import=proof([5]),
            nested_imports=[dict(API=a,refused=True,error='Nested context') for a in ['generic_compute','generic_graphics','certified_CAS','invalid_CAS']],
            concurrent_imports=[dict(kind=0,expected_cached_refusal=True,pipeline_created=False,
                error='Decoded program contract did not match',proof=dict(contract_verified=False,constructor_restored=True,
                    target_imports=0,verified_imports=0,rejected_import=False)),
                dict(kind=1,expected_cached_refusal=False,pipeline_created=True,proof=proof([0,4])),
                dict(kind=2,expected_cached_refusal=False,pipeline_created=True,proof=dict(constructor_restored=True,native_import=proof([5])))])

    def test_exact_expected_cache_refusal(self):
        self.assertEqual(oracle.verify_contract(self.contract_fixture())['cached_pipeline_refusals'],1)

    def test_unexpected_positive_or_import_failure_not_masked(self):
        for change in ['positive','wrong_failure']:
            r=self.contract_fixture()
            if change=='positive':r['concurrent_imports'][0]['pipeline_created']=True
            else:r['concurrent_imports'][0]['proof']['target_imports']=1
            with self.assertRaises(AssertionError):oracle.verify_contract(r)


if __name__ == '__main__':unittest.main()
