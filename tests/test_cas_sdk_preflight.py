# SPDX-License-Identifier: MIT
"""The SDK builder must refuse an unqualified driver before creating output."""
import runpy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BRIDGE = Path(__file__).resolve().parents[1] / 'bridge'
sys.path.insert(0, str(BRIDGE / 'tools'))
import public_large_scratch

class CASSDKPreflight(unittest.TestCase):
    def test_unqualified_driver_refused_before_output(self):
        results = BRIDGE / 'results'
        results.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='sdk-profile-test-', dir=results) as folder:
            out = Path(folder) / 'sdk'
            argv = ['prepare_native_cas_sdk.py', '--out', str(out)]
            with mock.patch.object(public_large_scratch, 'check_driver_profile', side_effect=RuntimeError('unqualified driver')), mock.patch.object(sys, 'argv', argv):
                with self.assertRaisesRegex(RuntimeError, 'unqualified driver'):
                    runpy.run_path(str(BRIDGE / 'tools/prepare_native_cas_sdk.py'), run_name='__main__')
            self.assertFalse(out.exists())

    def test_module_requires_decoder_evidence_before_output(self):
        results = BRIDGE / 'results'
        results.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='sdk-evidence-test-', dir=results) as folder:
            root = Path(folder); assets = root / 'assets'; assets.mkdir()
            library = assets / 'library.metallib'; library.write_bytes(b'fixture')
            cert = assets / 'certificate.json'; cert.write_text(json.dumps({'candidate': True, 'decoder_reproduced_listing': 'true'}))
            digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            manifest = {'library': library.name, 'library_SHA256': digest(library), 'driver_SHA256': 'qualified-fixture',
                        'profiles': [{'candidate': True, 'certificate': cert.name, 'certificate_SHA256': digest(cert)}]}
            (assets / 'client-manifest.json').write_text(json.dumps(manifest))
            out = root / 'sdk'
            argv = ['build_native_cas_sdk_module.py', '--assets-from', str(assets), '--out', str(out), '--require-decoder-evidence']
            with mock.patch.object(public_large_scratch, 'check_driver_profile', return_value='qualified-fixture'), mock.patch.object(sys, 'argv', argv):
                with self.assertRaisesRegex(SystemExit, 'decoder reproduction'):
                    runpy.run_path(str(BRIDGE / 'tools/build_native_cas_sdk_module.py'), run_name='__main__')
            self.assertFalse(out.exists())

if __name__ == '__main__': unittest.main()
