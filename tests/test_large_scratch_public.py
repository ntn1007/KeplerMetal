"""Portable rejection checks; these never create a Metal device or GPU job."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

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
