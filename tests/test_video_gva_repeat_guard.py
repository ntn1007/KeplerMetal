# SPDX-License-Identifier: MIT
import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

path = Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_repeat_sessions/audit_one_shot.py'
spec = importlib.util.spec_from_file_location('repeat_guard_audit',path)
audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)


class OneShotAuditTest(unittest.TestCase):
    def test_unpinned_source_refused(self):
        with self.assertRaisesRegex(ValueError,'source pin differs'): audit.static_guard(b'not a profile')

    def test_missing_guard_refused_even_when_digest_matches(self):
        class Hash:
            def hexdigest(self): return 'f5a4845045975c9deba0aca80c42d5a2216c64b72f37d234d3935b6a97f45db4'
        with patch.object(audit.hashlib,'sha256',return_value=Hash()):
            with self.assertRaisesRegex(ValueError,'guard sequence differs'): audit.static_guard(b'incomplete')


if __name__=='__main__': unittest.main()
