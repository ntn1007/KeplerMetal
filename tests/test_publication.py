import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

fetch = module('fetch_references')
policy = module('check_publication')

def fixture(path, members):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            if kind == 'link':
                info.type = tarfile.SYMTYPE
                info.linkname = '../../outside'
                archive.addfile(info)
            else:
                info.size = len(data)
                info.mode = 0o777
                archive.addfile(info, io.BytesIO(data))
    path.write_bytes(b'#!/bin/sh\nskip=4\nexit 99\n' + payload.getvalue())
    return hashlib.sha256(path.read_bytes()).hexdigest()

class PublicationTests(unittest.TestCase):
    def test_all_original_sources_match_manifest(self):
        manifest = json.loads((ROOT / 'SOURCE_SNAPSHOT.json').read_text())
        self.assertGreater(len(manifest['files']), 600)
        for row in manifest['files']:
            self.assertEqual(hashlib.sha256((ROOT / row['path']).read_bytes()).hexdigest(), row['published_SHA256'], row['path'])

    def test_extracts_text_without_executing_installer(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'fixture.run'
            pin = fixture(archive, [('package/source.c', b'int value;\n', 'file'), ('package/link', b'', 'link')])
            result = fetch.extract_reference(archive, root / 'extracted', pin)
            source = root / 'extracted/package/source.c'
            self.assertEqual(source.read_bytes(), b'int value;\n')
            self.assertEqual(source.stat().st_mode & 0o111, 0)
            self.assertFalse((root / 'extracted/package/link').exists())
            self.assertFalse(result['installer_executed'])
            self.assertTrue(any(x.get('skipped') == 'link_or_special_file' for x in result['files']))

    def test_wrong_hash_refuses_before_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'fixture.run'
            fixture(path, [('file', b'x', 'file')])
            with self.assertRaises(ValueError):
                fetch.extract_reference(path, root / 'out', '0' * 64)
            self.assertFalse((root / 'out').exists())

    def test_traversal_never_writes_outside(self):
        for name in ['../outside', '/absolute', 'part/../../outside', 'C:/outside', 'part\\outside']:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                path = root / 'fixture.run'
                pin = fixture(path, [(name, b'bad', 'file')])
                with self.assertRaises(ValueError):
                    fetch.extract_reference(path, root / 'out', pin)
                self.assertFalse((root / 'outside').exists())

    def test_existing_output_is_not_rewritten(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / 'fixture.run'
            pin = fixture(path, [('file', b'x', 'file')])
            destination = root / 'out'
            destination.mkdir()
            with self.assertRaises(FileExistsError):
                fetch.extract_reference(path, destination, pin)

    def test_reference_urls_are_official_and_hashes_are_pinned(self):
        rows = json.loads((ROOT / 'dependencies/references.json').read_text())['nvidia_linux']
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(fetch.checked_https(row['url']), row['url'])
            self.assertRegex(row['SHA256'], r'^[a-f0-9]{64}$')
        for bad in ['http://download.nvidia.com/file', 'https://example.com/file', 'https://user:secret@download.nvidia.com/file']:
            with self.assertRaises(ValueError):
                fetch.checked_https(bad)

    def test_binary_and_secret_markers_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            binary = root / 'driver.bin'
            binary.write_bytes(bytes([0xcf, 0xfa, 0xed, 0xfe, 0]))
            self.assertTrue(policy.inspect_file(binary, Path('driver.bin')))
            text = root / 'notes.md'
            text.write_text('gh' + 'p_' + 'x' * 40)
            self.assertIn('github-token', policy.inspect_file(text, Path('notes.md')))

if __name__ == '__main__':
    unittest.main()
