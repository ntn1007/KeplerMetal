# SPDX-License-Identifier: MIT
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'bridge/experiments/video_dpb_observation/observe.py'
spec = importlib.util.spec_from_file_location('dpb_observation', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SnapshotTests(unittest.TestCase):
    def test_interleaved_contexts_and_long_term(self):
        log = '''[h264 @ 0x11] short term list:
[h264 @ 0x11] 0 fn:4 poc:65544 0x123
[h264 @ 0x22] short term list:
[h264 @ 0x22] long term list:
[h264 @ 0x11] long term list:
[h264 @ 0x11] 2 fn:1 poc:65538 0x456
[h264 @ 0x22] slice:1 F mb:0 I IDR frame:0 poc:65536/65536 ref:0/0 qp:25
[h264 @ 0x11] slice:1 F mb:0 P frame:5 poc:65546/65546 ref:1/1 qp:26
'''
        rows = module.snapshots(log)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['short'], [])
        self.assertEqual(rows[1]['short'], [(0, 4, 65544, '0x123')])
        self.assertEqual(rows[1]['long'], [(2, 1, 65538, '0x456')])

    def test_no_stale_or_incomplete_snapshot(self):
        log = '''[h264 @ 0x11] short term list:
[h264 @ 0x11] long term list:
[h264 @ 0x11] slice:1 F mb:0 P frame:1 poc:65538/65538 ref:1/1 qp:26
[h264 @ 0x11] slice:2 F mb:150 P frame:1 poc:65538/65538 ref:1/1 qp:26
[h264 @ 0x11] short term list:
[h264 @ 0x11] slice:2 F mb:150 P frame:1 poc:65538/65538 ref:1/1 qp:26
'''
        self.assertEqual(len(module.snapshots(log)), 1)


if __name__ == '__main__':
    unittest.main()
