# SPDX-License-Identifier: MIT
"""Exercise the offline Mach-O video-table drift detector with synthetic data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'bridge/tools/compare_video_profile.py'
spec = importlib.util.spec_from_file_location('compare_video_profile', MODULE)
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


def fixture():
    data = bytearray(0x500)
    struct.pack_into('<8I', data, 0, 0xfeedfacf, 0x01000007, 3, 2, 3, 176, 0, 0)
    struct.pack_into('<II', data, 32, 0x19, 72)
    struct.pack_into('<QQQQ', data, 32+24, 0x1000, len(data), 0, len(data))
    struct.pack_into('<6I', data, 104, 2, 24, 0x380, 1, 0x390, 32)
    fields = [0]*20
    fields[0],fields[1],fields[16],fields[17] = 11,80,0x3c0,1
    struct.pack_into('<20I', data, 128, *fields)
    struct.pack_into('<IBBHQ', data, 0x380, 1, 1, 0, 0, 0)
    data[0x390:0x399] = b'\0_symbol\0'
    struct.pack_into('<II', data, 0x3c0, 0x1200, (3<<25)|(1<<27))
    rows = []
    for i in range(28):
        cell = 0x1200+i*8
        value = 0 if i == 0 else 0x2000+i
        struct.pack_into('<Q', data, 0x200+i*8, value)
        row = {'slot':hex(0x9e0+i*8),'cell_address':hex(cell),'original_word':hex(value)}
        if i == 0:
            row['external_relocation'] = {'address':cell,'file_offset':0x3c0,
                'pc_relative':0,'length_code':3,'external':1,'type':0,
                'symbol':{'name':'_symbol','type':1,'section':0,'description':0,'value':0,'index':0}}
        rows.append(row)
    return rows, bytes(data)


class VideoProfileComparison(unittest.TestCase):
    def test_matching_original_words_and_relocations(self):
        rows,data = fixture()
        result = profile.compare_slots(rows,data)
        self.assertEqual(result['slots_matching'],28)
        self.assertFalse(result['relocated_runtime_words_compared'])

    def test_changed_word_isolated(self):
        rows,data = fixture(); data=bytearray(data);data[0x210] ^= 1
        result = profile.compare_slots(rows,bytes(data))
        self.assertEqual(result['slots_matching'],27)
        self.assertEqual(result['slots_different'],[{'slot':rows[2]['slot'],'word_matches':False,'relocation_metadata_matches':True}])

    def test_changed_external_symbol_is_not_silently_accepted(self):
        rows,data = fixture(); data=bytearray(data);data[0x392] = ord('X')
        result = profile.compare_slots(rows,bytes(data))
        self.assertEqual(result['slots_matching'],27)
        self.assertFalse(result['slots_different'][0]['relocation_metadata_matches'])

    def test_duplicate_cells_refused(self):
        rows,data = fixture();rows[-1]['cell_address']=rows[0]['cell_address']
        with self.assertRaisesRegex(ValueError,'incomplete'): profile.compare_slots(rows,data)

    def test_function_range_change_is_detected(self):
        _,data = fixture()
        functions=[]
        for i in range(11):
            start=0x1300+i*4; offset=0x300+i*4; chunk=data[offset:offset+4]
            functions.append({'address':hex(start),'binary_SHA256':profile.LEGACY_SHA,
                'ranges':[{'start':hex(start),'end':hex(start+3),'bytes':4,
                           'file_offset':offset,'SHA256':hashlib.sha256(chunk).hexdigest()}]})
        dossier=[{'bundle':'GeForce-video-methods.private.json','functions':functions}]
        self.assertEqual(profile.compare_ranges(dossier,data)['ranges_matching'],11)
        altered=bytearray(data);altered[0x300+4*3] ^= 1
        result=profile.compare_ranges(dossier,bytes(altered))
        self.assertEqual(result['ranges_matching'],10)
        self.assertEqual(result['differences'][0]['function_address'],functions[3]['address'])

    def test_function_evidence_requires_same_subject_and_provider(self):
        def record(digest):
            return {'subject':{'digest':{'sha256':digest}},'operation':'analyze_function',
                    'analysis_profile':{'digest':'profile'},'provider':{'id':'ghidra'},
                    'evidence_id':'ev_test','normalized_result':{
                        'procedure':{'address':'0x68352','body':{'ranges':[]}},
                        'assembly':['instruction'],'pseudocode':'representation',
                        'outgoing_references':[]}}
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);prior=root/'prior.json';current=root/'current.json'
            prior.write_text(json.dumps({'records':[record(profile.LEGACY_SHA)]}))
            current.write_text(json.dumps(record('new-digest')))
            with patch.object(profile,'PRIOR_REA_SHA',profile.sha_file(prior)):
                self.assertTrue(profile.compare_function(prior,current,'new-digest')['assembly_match'])
                altered=record('new-digest');altered['provider']={'id':'other'}
                current.write_text(json.dumps(altered))
                with self.assertRaisesRegex(ValueError,'identity, provider or analysis profile'):
                    profile.compare_function(prior,current,'new-digest')

    def test_historical_input_is_hash_pinned(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'fake.json';p.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Historical evidence hash mismatch'):
                profile.compare(p,p,p)

if __name__ == '__main__': unittest.main()
