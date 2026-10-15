#!/usr/bin/env python3
"""Fail closed on binary/proprietary payloads, private identifiers or secrets."""
from pathlib import Path
import ast
import hashlib
import json
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SUFFIXES = {'.py', '.mm', '.cpp', '.c', '.h', '.inc', '.metal', '.metalh', '.patch',
            '.json', '.md', '.txt', '.yml', '.yaml', '.toml'}
SPECIAL_NAMES = {'LICENSE', '.gitignore'}
DENIED_PARTS = {'.ssh', '.codex', 'vendor', 'downloads', 'extracted', 'archives',
                'results', 'build', 'logs', 'inventory', 'comparison', 'evidence-private'}
PATTERNS = [
    ('private-key', re.compile(r'-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----')),
    ('github-token', re.compile(r'\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b')),
    ('api-key', re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}\b|\bAKIA[A-Z0-9]{16}\b')),
    ('private-home-path', re.compile(r'/Users/[A-Za-z0-9_.-]+/|[A-Z]:\\Users\\')),
    ('private-network', re.compile(r'\b(?:100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])|192\.168|10\.\d{1,3})\.\d{1,3}\.\d{1,3}\b|[A-Za-z0-9_.-]+\.ts\.net\b')),
]

def publication_files(root=ROOT):
    if (root / '.git').exists():
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'], capture_output=True, check=True)
        return [root / p.decode('utf-8') for p in result.stdout.split(b'\0') if p]
    return [p for p in root.rglob('*') if p.is_file() and not any(part in DENIED_PARTS or part == '.git' or part == '__pycache__' for part in p.relative_to(root).parts)]

def inspect_file(path, relative):
    errors = []
    if path.is_symlink() or any(x in DENIED_PARTS or x.endswith(('.kext', '.bundle', '.framework')) for x in relative.parts):
        errors.append('excluded path or link')
    if path.suffix not in SUFFIXES and path.name not in SPECIAL_NAMES:
        errors.append('non-source file extension')
    data = path.read_bytes()
    try:
        text = data.decode('utf-8')
    except UnicodeDecodeError:
        return errors + ['non-UTF-8 payload']
    if b'\0' in data or len(data) > 2 * 1024 * 1024:
        errors.append('binary marker or oversized payload')
    for name, pattern in PATTERNS:
        if pattern.search(text):
            errors.append(name)
    if path.suffix == '.py':
        try:
            ast.parse(text, filename=str(relative))
        except SyntaxError as exc:
            errors.append(f'Python syntax at line {exc.lineno}')
    return errors

def main():
    failures = []
    files = publication_files()
    if not files:
        raise SystemExit('FAIL: no publication files were selected.')
    for path in files:
        errors = inspect_file(path, path.relative_to(ROOT))
        if errors:
            failures.append({'path': str(path.relative_to(ROOT)), 'errors': errors})
    manifest = json.loads((ROOT / 'SOURCE_SNAPSHOT.json').read_text())
    for row in manifest['files']:
        path = ROOT / row['path']
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['published_SHA256']:
            failures.append({'path': row['path'], 'errors': ['source snapshot mismatch']})
    print(json.dumps({'status': 'FAIL' if failures else 'PASS', 'files_checked': len(files),
                      'source_snapshot_files': len(manifest['files']), 'failures': failures}, indent=2))
    return bool(failures)

if __name__ == '__main__':
    sys.exit(main())
