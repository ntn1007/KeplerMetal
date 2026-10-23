"""CPU-only ledger contract tests. Fixtures are not hardware observations."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('local_oracle', Path(__file__).resolve().parents[1] / 'bridge/tools/verify_local_memory.py')
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def record(imported=True, dispatch=True, pressure=False):
    name = 'pressure96' if pressure else 'local4096'
    array = 0 if pressure else 16384
    carrier = 224 if pressure else array
    row = dict(requested_private_bytes=17536, requested_shared_bytes=17552,
        source_array_bytes_per_thread=array, logical_array_bytes=32*array if dispatch else 0,
        imported_carrier_bytes_per_thread=carrier if imported else None,
        required_scratch_bytes_per_thread=224 if pressure and imported else (array if imported else None),
        logical_carrier_bytes=(32*carrier if dispatch else 0) if imported else None,
        allocated_before_buffers=100000, allocated_after_buffers=140000,
        allocated_after_completion=130000, allocated_after_release=99000)
    return dict(function=name, mode=('nak:' if imported else '')+('' if dispatch else 'no_dispatch:')+name,
        program_info=dict(scratch_bytes=carrier),
        memory_ledger=dict(schema=1,buffer_request_cap_bytes=8*1024**2,logical_local_cap_bytes=64*1024**2,
            allocated_before_trials=100000,allocated_after_trials=99000,
            physical_VRAM_measured=False,scratch_occupancy_measured=False,maximum_pressure_measured=False),
        runs=[dict(threads=32,input_bytes=16768,output_bytes=768,memory_ledger=row)])


class MemoryLedgerTests(unittest.TestCase):
    def identity(self, registry=4294968456):
        return dict(device='NVIDIA GeForce GTX 880M',registry_id=registry,device_identity=dict(schema=1,
            name='NVIDIA GeForce GTX 880M',registry_id=registry,PCI_registry_id=4294967841,
            PCI_vendor_id=0x10de,PCI_device_id=0x1198))

    def test_identity_survives_boot_entry_changes(self):
        for entry in [4294968456,4294968458,4294969000]:oracle.verify_device_identity(self.identity(entry))

    def test_wrong_pci_device_rejected(self):
        for key,value in [('PCI_vendor_id',0x8086),('PCI_device_id',0xe0a)]:
            with self.subTest(key=key):
                d=self.identity();d['device_identity'][key]=value
                with self.assertRaises(AssertionError):oracle.verify_device_identity(d)

    def test_identity_registry_mismatch_rejected(self):
        d=self.identity();d['registry_id']+=1
        with self.assertRaises(AssertionError):oracle.verify_device_identity(d)

    def test_identity_missing_pci_rejected(self):
        d=self.identity();del d['device_identity']['PCI_registry_id']
        with self.assertRaises(KeyError):oracle.verify_device_identity(d)

    def test_old_identity_keeps_old_contract(self):
        oracle.verify_device_identity(dict(device='NVIDIA GeForce GTX 880M',registry_id=4294968458))
        with self.assertRaises(AssertionError):oracle.verify_device_identity(dict(device='NVIDIA GeForce GTX 880M',registry_id=4294968456))

    def test_identity_gpu_name_rejected(self):
        d=self.identity();d['device']='different GPU'
        with self.assertRaises(AssertionError):oracle.verify_device_identity(d)

    def test_complete_accounting(self):
        result = oracle.verify_memory_ledger(record(), required=True)
        self.assertEqual(result['logical_carrier_bytes_max'], 524288)
        self.assertEqual(result['requested_private_bytes_max'], 17536)
        self.assertEqual(result['accounting_samples'], 4)

    def test_native_frame_is_unknown(self):
        result = oracle.verify_memory_ledger(record(imported=False), True)
        self.assertIsNone(result['logical_carrier_bytes_max'])
        self.assertEqual(result['logical_array_bytes_max'], 524288)

    def test_pressure_array_differs_from_import_frame(self):
        result = oracle.verify_memory_ledger(record(pressure=True), True)
        self.assertEqual(result['logical_array_bytes_max'], 0)
        self.assertEqual(result['logical_carrier_bytes_max'], 7168)

    def test_no_dispatch_has_no_logical_invocation_demand(self):
        result = oracle.verify_memory_ledger(record(dispatch=False), True)
        self.assertEqual(result['logical_array_bytes_max'], 0)
        self.assertEqual(result['logical_carrier_bytes_max'], 0)

    def test_missing_counter_is_not_zero(self):
        d = record()
        for key in list(d['runs'][0]['memory_ledger']):
            if key.startswith('allocated_'): d['runs'][0]['memory_ledger'][key] = None
        result = oracle.verify_memory_ledger(d, True)
        self.assertEqual(result['unsupported_samples'], 4)
        self.assertIsNone(result['API_completion_delta_bytes_min'])

    def test_negative_accounting_delta_is_preserved(self):
        d = record(); d['runs'][0]['memory_ledger']['allocated_after_completion'] = 90000
        self.assertEqual(oracle.verify_memory_ledger(d)['API_completion_delta_bytes_min'], -10000)

    def test_historical_records_remain_readable(self):
        d = record(); del d['memory_ledger']; del d['runs'][0]['memory_ledger']
        self.assertEqual(oracle.verify_memory_ledger(d)['status'], 'NOT_RECORDED')
        with self.assertRaises(AssertionError): oracle.verify_memory_ledger(d, True)

    def test_corrupt_or_misleading_fields_rejected(self):
        for key, value in [('requested_private_bytes',17535),('requested_shared_bytes',17551),
                ('source_array_bytes_per_thread',8192),('logical_array_bytes',0),
                ('imported_carrier_bytes_per_thread',8192),('required_scratch_bytes_per_thread',0),
                ('logical_carrier_bytes',0),('allocated_before_buffers',-1),
                ('allocated_after_buffers',True),('allocated_after_completion',1.5)]:
            with self.subTest(key=key):
                d = record(); d['runs'][0]['memory_ledger'][key] = value
                with self.assertRaises(AssertionError): oracle.verify_memory_ledger(d, True)

    def test_missing_phase_rejected(self):
        d = record(); del d['runs'][0]['memory_ledger']['allocated_after_release']
        with self.assertRaises(KeyError): oracle.verify_memory_ledger(d, True)

    def test_stripped_header_rejected(self):
        d = record(); del d['memory_ledger']
        with self.assertRaises(AssertionError): oracle.verify_memory_ledger(d)

    def test_claims_and_caps_rejected(self):
        for key,value in [('schema',2),('buffer_request_cap_bytes',16*1024**2),
                ('logical_local_cap_bytes',128*1024**2),('physical_VRAM_measured',True),
                ('scratch_occupancy_measured',True),('maximum_pressure_measured',True)]:
            with self.subTest(key=key):
                d = record(); d['memory_ledger'][key] = value
                with self.assertRaises(AssertionError): oracle.verify_memory_ledger(d)

    def test_over_cap_request_rejected(self):
        d = record(); d['runs'][0]['threads'] = 8192
        row=d['runs'][0]['memory_ledger']; row['logical_array_bytes']=row['logical_carrier_bytes']=8192*16384
        with self.assertRaises(AssertionError): oracle.verify_memory_ledger(d)


if __name__ == '__main__': unittest.main()
