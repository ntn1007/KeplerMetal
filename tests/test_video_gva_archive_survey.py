# SPDX-License-Identifier: MIT
"""Exercise bounded archive scanning without vendor data or GPU execution."""
import importlib.util
import io
import plistlib
import stat
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_archive_survey/survey.py'
spec = importlib.util.spec_from_file_location('survey', path)
survey = importlib.util.module_from_spec(spec)
spec.loader.exec_module(survey)


def entry(name, data, mode=stat.S_IFREG | 0o644):
    name = name.encode() + b'\0'
    fields = ((0,6),(0,6),(mode,6),(0,6),(0,6),(1,6),(0,6),(0,11),(len(name),6),(len(data),11))
    return b'070707' + b''.join(f'{value:0{width}o}'.encode() for value, width in fields) + name + data


def archive(*members):
    return b''.join(members) + entry('TRAILER!!!', b'') + b'\0'*17


class SurveyTest(unittest.TestCase):
    def test_encodings_across_small_chunks_and_plist_value(self):
        plist = plistlib.dumps({'IOGVACodec': 'test-value'}, fmt=plistlib.FMT_BINARY)
        data = archive(entry('./one', b'x'*7 + b'IOGVACodec' + b'Y' + 'IOGVACodec'.encode('utf-16le') + b'Z' + 'IOGVACodec'.encode('utf-16be')),
                       entry('./two.plist', plist), entry('./link', b'IOGVACodec', stat.S_IFLNK | 0o777))
        result = survey.scan(io.BytesIO(data), len(data), chunk_size=8)
        self.assertEqual(result['regular_members'], 2)
        self.assertEqual(len(result['matches']), 2)
        self.assertEqual(result['matches'][0]['literal_counts'], {'ascii': 1, 'utf16le': 1, 'utf16be': 1})
        self.assertEqual(result['matches'][1]['plist_key_values'], [{'type': 'str', 'string': 'test-value'}])
        self.assertEqual(result['trailing_bytes'], 17)

    def test_duplicate_and_truncated_members_rejected(self):
        data = archive(entry('./same', b'a'), entry('./same', b'b'))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            survey.scan(io.BytesIO(data), len(data), chunk_size=9)
        data = archive(entry('./x', b'payload'))[:-90]
        with self.assertRaises(ValueError):
            survey.scan(io.BytesIO(data), len(data), chunk_size=9)


if __name__ == '__main__':
    unittest.main()
