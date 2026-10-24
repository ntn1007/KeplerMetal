"""Falsify archived readbacks offline; no Metal device or GPU submission."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from verify_indirect_render_ranges import MODES, expected_buffers, requested, verify_rows, expected_record, record_reason, values


def fixture(root, mode='gpu'):
    root = Path(root)
    outputs = root / 'outputs'
    outputs.mkdir()
    reference = mode == 'native' or mode.endswith('_native')
    legacy = mode.startswith('legacy')
    fragment = mode.startswith('fragment')
    records = 'records' in mode
    no_producer = mode == 'records_no_producer'
    consumer = mode not in ['no_consumer','records_no_consumer']
    assert not fragment  # Fragment arithmetic has separate fixed-value checks below.
    ranges = [(0, 4), (3, 1), (0, 2), (3, 1), (1, 0), (5, 0), (0xfffffffe, 3), (0, 0)]
    selected = [[0, 1, 3], [3], [0, 1], [3], [], [], [], []]
    if records:
        ranges = [(0,4)]*7+[(0,0)]
        selected = [[0,1,3],[0,3],[0,1],[1,3],[0,3],[0,1],[1,3],[]]
        if no_producer:ranges,selected=[(0,0)]*8,[[]for _ in range(8)]
    templates = [[6, 1, 5, 0, 0], [6, 1, 0, 2, 1], [0]*5, [6, 1, 0, 0xfffffffe, 2]]
    if legacy:
        templates = [[3, 1, 0, 0, 0], [3, 1, 0, 0, 0], [0]*5, [3, 1, 0, 0, 0]]
    rows, events = [], []
    refusals = ['pending_reprepare', 'misaligned_range', 'short_range', 'foreign_queue',
                'unretained_command_buffer', 'wrong_kernel_pin', 'wrong_range_object',
                'wrong_range_offset', 'copied_ICB_has_no_preparation', 'mutated_command',
                'duplicate_execution']
    for trial in range(8):
        assert requested(trial, records, no_producer) == ranges[trial]
        prefix = outputs / ('trial-%d' % trial)
        for index, raw in enumerate(expected_buffers(trial, legacy, records, no_producer)):
            Path(str(prefix) + '.buffer-%d.bin' % index).write_bytes(raw)
        if not reference:
            args, witness = bytearray(b'\xa5'*256), bytearray(b'\xa5'*192)
            for slot in range(4):
                struct.pack_into('<5I', args, 64 + slot*32,
                                 *((expected_record(trial,slot)[2:7] if records else templates[slot]) if slot in selected[trial] else [0]*5))
                struct.pack_into('<4I', witness, 64 + slot*16,
                                 int(records or trial not in (5, 6)), int(slot in selected[trial]),
                                 [0, 1, 0, 2][slot], (0x4b520000|record_reason(trial,slot,not no_producer and trial!=7))if records else 0x4b505247)
            Path(str(prefix) + '.arguments.bin').write_bytes(args)
            Path(str(prefix) + '.witness.bin').write_bytes(witness)
            events.append(dict(operation='prepare_GPU_indirect_render_range', GPU_generated_draw_records=records))
            if consumer:
                events.append(dict(operation='execute_GPU_indirect_render_range', slot_capacity=4, GPU_generated_draw_records=records, record_CPU_read=False,
                    range_offset=64, range_CPU_read=False, caller_pipeline_restored=True,
                    caller_vertex_slots_restored=0 if legacy else 2, caller_fragment_slots_restored=0,
                    evidence=dict(operation='native_GPU_range_indirect_draws', range_CPU_read=False,
                        draw_arguments_CPU_read=False, raw_record_copies=0, system_modified=False,
                        resource_leases_until_completion=True,
                        draw_calls=[dict(slot=i, kind=k, argument_offset=o)
                                    for i, k, o in [(0, 0, 64), (1, 1, 96), (3, 2, 160)]])))
        pixels = []
        for y in range(48):
            for x in range(64):
                c = (0, 0, 0, 0)
                inside = not trial % 2 or (3 <= x < 60 and 4 <= y < 43)
                if inside:
                    if consumer:
                        for slot in selected[trial]:
                            if legacy: c = (.75, .125, .25, 1)
                            elif slot == 0 and x < 32: c = (.25, .125, .75, 1)
                            elif slot == 1 and x >= 32: c = (.125, .75, .265625, 1)
                            elif slot == 3 and 16 <= x < 48 and 12 <= y < 36: c = (.75, .5, .15625, 1)
                    if records and x>=8:
                        # Independent half-plane raster, using normalized pixel centers.
                        c=(0,0,0,0)
                        if consumer:
                            for slot in selected[trial]:
                                x0,y0,x1,y1,color={0:(0,0,32,48,(.25,.125,.75,1)),1:(32,0,64,48,(.125,.75,.265625,1)),3:(16,12,48,36,(.75,.5,.15625,1))}[slot]
                                if x0<=x<x1 and y0<=y<y1:
                                    kind={0:0,1:1,3:2}[slot];v=values(trial)[(trial*5+3)%16]
                                    side=(x+.5-x0)/(x1-x0)>(y+.5-y0)/(y1-y0)
                                    if side==bool((v>>kind)&1):c=color
                    if x < 8: c = (.875, .625, .625, 1)
                pixels.extend(c)
        Path(str(prefix) + '.image.bin').write_bytes(b'\xa5'*256 + struct.pack('<12288f', *pixels) + b'\xa5'*256)
        rows.append(dict(trial=trial, command_status=4, expected_range=list(ranges[trial]),
            native_reference=reference, consumer_encoded=consumer,
            producer_dispatches=int(trial != 7 and not no_producer), fragment_resources=False, legacy_geometry=legacy,
            inline_marker_parameter=bool(trial % 2), scissor=[3, 4, 57, 39] if trial % 2 else [0, 0, 64, 48],
            ICB_object_identity=99, released_before_commit=mode == 'lifetime' and trial == 7,
            classes_restored_before_commit=mode == 'lifetime' and trial == 7,
            api_refusals=refusals.copy() if mode == 'contracts' and trial < 2 else []))
    if mode.endswith('release'):
        rows=rows[:1];events=events[:2]
        rows[0].update(released_before_commit=True, classes_restored_before_commit=True, autorelease_pool_drained_before_commit=True, scope_deallocated_before_commit=True, ICB_deallocated_before_commit=True, fragment_texture_alive_before_commit=False, fragment_sampler_alive_before_commit=False)
    if mode == 'contracts': rows[1]['api_refusals'][9] = 'reset_command'
    return dict(device='NVIDIA GeForce GTX 880M', registry_id=1,
        device_identity=dict(schema=1, name='NVIDIA GeForce GTX 880M', registry_id=1,
                             PCI_registry_id=2, PCI_vendor_id=0x10de, PCI_device_id=0x1198),
        status='COMPLETED', scope_restored=True, range_CPU_read_before_render=False,
        performance_benchmark=False, CPU_resolved_range_supplied=reference,
        mode=mode, runs=rows, scope_events=events)


class IndirectRenderEvidence(unittest.TestCase):
    def test_nonfragment_modes(self):
        for mode in MODES:
            if mode.startswith('fragment'): continue
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as path:
                d = fixture(path, mode)
                self.assertEqual(verify_rows(d, path)['checked_float_channels'], 12288 if mode.endswith('release') else 98304)

    def corrupt(self, suffix, offset, word=None, mode='gpu', trial=0):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path); d = fixture(root, mode)
            p = root / 'outputs' / ('trial-%d.' % trial + suffix + '.bin')
            raw = bytearray(p.read_bytes())
            if word is None: raw[offset] ^= 1
            else: struct.pack_into('<I', raw, offset, word)
            p.write_bytes(raw)
            with self.assertRaises(AssertionError): verify_rows(d, root)

    def test_wrong_draw_count(self): self.corrupt('arguments', 64, 5)
    def test_wrong_signed_base_vertex(self): self.corrupt('arguments', 64+3*32+12, 2)
    def test_empty_slot_cannot_draw(self): self.corrupt('arguments', 64+2*32, 6)
    def test_argument_padding_guard(self): self.corrupt('arguments', 64+20)
    def test_argument_end_guard(self): self.corrupt('arguments', 255)
    def test_witness_selection(self): self.corrupt('witness', 64+16+4, 0)
    def test_witness_magic(self): self.corrupt('witness', 64+12)
    def test_range_input(self): self.corrupt('buffer-9', 64, 1)
    def test_private_vertex_input(self): self.corrupt('buffer-1', 64+7*32)
    def test_image_guard(self): self.corrupt('image', 49663)
    def test_pixel_nan(self): self.corrupt('image', 256+20*4, 0x7fc00000)
    def test_caller_state_restoration(self): self.corrupt('image', 256+4, 0x3e800000)
    def test_skipped_consumer_cannot_show_draw(self): self.corrupt('image', 256+24*16, 0x3f800000, 'no_consumer')

    def test_expected_refusal_names(self):
        with tempfile.TemporaryDirectory() as path:
            d = fixture(path, 'contracts'); d['runs'][0]['api_refusals'][0] = 'different_test'
            with self.assertRaises(AssertionError): verify_rows(d, path)

    def test_cpu_read_cannot_be_claimed_gpu_driven(self):
        with tempfile.TemporaryDirectory() as path:
            d = fixture(path); d['range_CPU_read_before_render'] = True
            with self.assertRaises(AssertionError): verify_rows(d, path)

    def test_gpu_record_source_is_checked(self): self.corrupt('buffer-11',64,0,mode='records')
    def test_gpu_record_rejection_reason(self): self.corrupt('witness',64+16+12,0x4b520000,mode='records',trial=1)
    def test_oversized_gpu_count_must_not_reach_native_draw(self): self.corrupt('arguments',64,0xfffffffe,mode='records',trial=3)
    def test_missing_record_producer_cannot_be_replaced_with_cpu_data(self): self.corrupt('buffer-11',64,0x4b505244,mode='records_no_producer')
    def test_weak_scope_observation_required_after_pool_drain(self):
        for key in ['scope_deallocated_before_commit','ICB_deallocated_before_commit','autorelease_pool_drained_before_commit']:
            with self.subTest(key=key),tempfile.TemporaryDirectory()as path:
                d=fixture(path,'release');d['runs'][0][key]=False
                with self.assertRaises(AssertionError):verify_rows(d,path)

    def test_fixed_fragment_samples(self):
        from verify_indirect_render_ranges import texel, fragment_color
        self.assertEqual(texel(0, 0, 0), (0, 0, 0, 1))
        self.assertEqual(texel(1, 0, 0), (.875, .875, 0, 1))
        self.assertEqual(fragment_color(0, 0, 0, (.25, .125, .75, 1)), (.125, 0, 0, 1))
        self.assertEqual(fragment_color(3, 1, 2, (.75, .5, .15625, 1)),
                         (.03515625, .03125, .30859375, 1))
        self.assertEqual(fragment_color(1, 0, 0, (.125, .75, .265625, 1)),
                         (.10546875, 1.091796875, .0103759765625, 1))


if __name__ == '__main__': unittest.main()
