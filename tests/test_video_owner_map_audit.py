# SPDX-License-Identifier: MIT
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from audit_video_context_owner_map import validate_observation


def sample():
    row = {'status': 'OWNER_MAP_COVERAGE_RECORDED', 'owner_qualified': True,
           'owner_registry_ID': 17, 'mapping_ranges_disjoint': True,
           'mapping_contents_read_or_written': False, 'explicit_unmap_calls': 0}
    for phase in ('before', 'after_open', 'after_associate', 'after_context_close', 'after_shared_close'):
        present = phase in ('after_open', 'after_associate')
        row['registry_' + phase] = {'status': 0, 'iterator_valid': True, 'truncated': False,
                                   'contexts': [{'id': 17, 'creator_matches_self_pid': True}] if present else []}
    for typ in (1, 2):
        row.update({'map%d_attempts' % typ: 1, 'map%d_status' % typ: 0,
                    'map%d_returned' % typ: True, 'map%d_bytes' % typ: 4096,
                    'type%d_before_close' % typ: 1, 'type%d_after_context_close' % typ: 0,
                    'type%d_after_shared_close' % typ: 0})
    return row


class OwnerMapAuditTests(unittest.TestCase):
    def test_success_and_fail_closed_controls(self):
        self.assertEqual(validate_observation(sample()), 17)
        changes = [lambda r: r.update(mapping_ranges_disjoint=False),
                   lambda r: r.update(type1_after_context_close=1),
                   lambda r: r.update(map2_bytes=8192),
                   lambda r: r.update(explicit_unmap_calls=1),
                   lambda r: r['registry_after_open']['contexts'][0].update(creator_matches_self_pid=False),
                   lambda r: r['registry_after_context_close']['contexts'].append({'id': 17, 'creator_matches_self_pid': False}),
                   lambda r: r['registry_after_associate'].update(iterator_valid=False)]
        for mutate in changes:
            row = copy.deepcopy(sample());mutate(row)
            with self.subTest(change=mutate), self.assertRaises(AssertionError):
                validate_observation(row)


if __name__ == '__main__':
    unittest.main()
