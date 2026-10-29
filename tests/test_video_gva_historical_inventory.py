import hashlib
import importlib.util
import io
import plistlib
import stat
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_gva_historical_inventory/audit.py'
SPEC = importlib.util.spec_from_file_location('historical_inventory', PATH)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def member(name, data, mode=stat.S_IFREG | 0o644):
    encoded = name.encode() + b'\0'
    fields = [0, 0, mode, 0, 0, 1, 0]
    header = ('070707' + ''.join('%06o' % x for x in fields) + '%011o%06o%011o' %
              (0, len(encoded), len(data))).encode()
    assert len(header) == 76
    return header + encoded + data


class HistoricalArchiveTest(unittest.TestCase):
    def test_bounded_members_key_and_literals(self):
        prefix = './System/Library/Extensions/GeForce.kext/Contents/'
        plist = plistlib.dumps({'IOKitPersonalities': {'Test': {'IOGVACodec': 'synthetic'}}})
        raw = (member(prefix + 'Info.plist', plist) + member(prefix + 'MacOS/GeForce', b'xIOGVACodecy') +
               member('TRAILER!!!', b'') + b'\0' * 13)
        result = audit.scan(io.BytesIO(raw), len(raw))
        self.assertEqual(result['archive_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result['records'], 3)
        self.assertEqual(result['trailing_bytes'], 13)
        self.assertEqual(result['nvidia_members'][0]['codec_key_paths'], 1)
        self.assertEqual(result['nvidia_members'][1]['ascii_occurrences'], 1)

    def test_duplicate_truncated_and_nonregular_are_refused(self):
        path = './System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce'
        trailer = member('TRAILER!!!', b'')
        duplicate = member(path, b'a') + member(path, b'b') + trailer
        nonregular = member(path, b'a', stat.S_IFLNK | 0o777) + trailer
        for data in (duplicate, nonregular, member(path, b'a')[:-1], b'garbage'):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                audit.scan(io.BytesIO(data), len(data))


if __name__ == '__main__':
    unittest.main()
