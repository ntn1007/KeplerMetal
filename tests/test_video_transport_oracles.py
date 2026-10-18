# SPDX-License-Identifier: MIT
"""Portable refusal/oracle checks; these tests execute no XPC or GPU program."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from audit_video_local_xpc import oracle, primer, cancellation


class VideoTransportOracles(unittest.TestCase):
    def test_uint32_rotation_and_overflow(self):
        self.assertEqual(oracle(0, 0, 0), 1013904223)
        self.assertEqual(oracle(0x80000000, 0, 0), 1013904224)
        self.assertEqual(oracle(0xffffffff, 0, 30), 1063839972)
        self.assertEqual(oracle(0x89abcdef, 0x13579, 0), 1338303628)

    def test_primer_rejects_wrong_value_and_sequence(self):
        valid = dict(kind='cancellation_primer', sequence=0xfedcba9876543210,
                     seed=0x13579, input_word=0x89abcdef, reply_word=1338303628, correct=True)
        primer(valid, valid['seed'])
        for field in ['sequence', 'input_word', 'reply_word', 'seed']:
            invalid = dict(valid); invalid[field] ^= 1
            with self.assertRaises(ValueError):
                primer(invalid, valid['seed'])

    def test_pending_cancellation_requires_all_observations(self):
        valid = dict(kind='pending_reply_cancellation', request_held=True,
                     reply_observed=True, reply_callbacks=1, known_error=True, correct=True)
        cancellation(valid)
        for field in ['request_held', 'reply_observed', 'known_error', 'correct']:
            invalid = dict(valid); invalid[field] = False
            with self.assertRaises(ValueError):
                cancellation(invalid)

    def test_duplicate_reply_is_not_a_success(self):
        invalid = dict(kind='pending_reply_cancellation', request_held=True,
                       reply_observed=True, reply_callbacks=2, known_error=True, correct=True)
        with self.assertRaises(ValueError):
            cancellation(invalid)


if __name__ == '__main__':
    unittest.main()
