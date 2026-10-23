"""Portable rejection checks; these never create a Metal device or GPU job."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('public_large_scratch', ROOT / 'bridge/tools/public_large_scratch.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(root):
    (root / 'src').mkdir()
    names = ['KeplerCPUICB', 'KeplerNativeCommands', 'KeplerNativeRenderDraws',
             'KeplerNativeCAS', 'KeplerFP64', 'KeplerProgramImport', 'KeplerCommandIRProducerFactory']
    for name in names:
        (root / 'src' / (name + '.mm')).write_bytes((ROOT / 'bridge/src' / (name + '.mm')).read_bytes())
        (root / (name + '.o')).write_bytes(('offline fixture ' + name).encode())
    (root / 'libKeplerMetal.a').write_bytes(b'offline archive fixture; never linked or executed')
    m = dict(status='PASS', architecture='x86_64', SDK='26.2',
        object_SHA256={name + '.o':sha(root / (name + '.o')) for name in names},
        source_SHA256={name + '.mm':sha(root / 'src' / (name + '.mm')) for name in names},
        static_library_SHA256=sha(root / 'libKeplerMetal.a'))
    (root / 'manifest.json').write_text(json.dumps(m))
    return m


class PublicLargeScratchTests(unittest.TestCase):
    def test_matching_driver_profile(self):
        for digest in tool.DRIVER_PROFILES:
            with self.subTest(digest=digest),patch.object(tool, 'sha', return_value=digest):
                self.assertEqual(tool.check_driver_profile(), digest)

    def test_changed_driver_profile_rejected(self):
        with patch.object(tool, 'sha', return_value='0'*64):
            with self.assertRaisesRegex(RuntimeError, 'GPU execution NOT RUN'):
                tool.check_driver_profile()

    def test_host_and_launcher_pin_agree(self):
        for digest in tool.DRIVER_PROFILES:
            self.assertIn(digest, (ROOT / 'bridge/tools/native_large_scratch_probe.mm').read_text())
            self.assertIn(digest, (ROOT / 'bridge/src/KeplerDriverProfile.h').read_text())

    def test_profile_refusal_creates_no_run_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); build = root / 'build'; build.mkdir()
            reservation = root / 'reservation'; (reservation / 'results').mkdir(parents=True)
            (build / 'application').write_bytes(b'offline fixture; never executed')
            (build / 'inputs.json').write_text(json.dumps(dict(execution_witness_magic=None,
                source_hashes={},assets_SHA256={},runtime_SHA256={},executable_SHA256=sha(build / 'application'))))
            a = SimpleNamespace(build=build,out=root / 'run',reservation_root=reservation,
                contracts=False,mode='nak:local4096')
            with patch.object(tool, 'check_driver_profile', side_effect=RuntimeError('profile changed')):
                with self.assertRaisesRegex(RuntimeError, 'profile changed'): tool.run(a)
            self.assertFalse(a.out.exists())
            self.assertEqual(list((reservation / 'results').iterdir()), [])

    def test_seven_object_provenance_accepts_matching_text(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); m = fixture(root)
            self.assertEqual(tool.check_library(root), m)

    def test_six_object_archive_is_not_public_qualification(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); m = fixture(root)
            del m['object_SHA256']['KeplerProgramImport.o']
            (root / 'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(AssertionError): tool.check_library(root)

    def test_changed_object_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); fixture(root)
            (root / 'KeplerNativeCAS.o').write_bytes(b'changed')
            with self.assertRaises(AssertionError): tool.check_library(root)

    def test_self_consistent_different_runtime_text_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); m = fixture(root)
            source = root / 'src/KeplerNativeCAS.mm'
            source.write_bytes(source.read_bytes() + b'\n// different runtime\n')
            m['source_SHA256']['KeplerNativeCAS.mm'] = sha(source)
            (root / 'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(AssertionError): tool.check_library(root)

    def test_changed_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); fixture(root)
            (root / 'libKeplerMetal.a').write_bytes(b'changed archive')
            with self.assertRaises(AssertionError): tool.check_library(root)


if __name__ == '__main__': unittest.main()
