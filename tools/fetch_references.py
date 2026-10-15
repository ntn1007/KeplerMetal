#!/usr/bin/env python3
"""Explicit, hash-pinned local reference retrieval; never execute installers."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import re
import shutil
import tarfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def checked_https(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname != 'download.nvidia.com' or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError('Reference retrieval accepts official NVIDIA HTTPS URLs only.')
    return url

class NVIDIAOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        checked_https(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)

def download_reference(item, destination):
    checked_https(item['url'])
    if destination.exists():
        if sha(destination) != item['SHA256']:
            raise ValueError('Existing download differs from the pinned hash; original left intact.')
        return
    partial = destination.with_name(destination.name + '.partial')
    opener = urllib.request.build_opener(NVIDIAOnlyRedirects())
    with opener.open(item['url'], timeout=30) as response, partial.open('xb') as output:
        checked_https(response.geturl())
        shutil.copyfileobj(response, output, 1024 * 1024)
    if sha(partial) != item['SHA256']:
        raise ValueError('Downloaded hash differs; partial preserved for inspection.')
    partial.chmod(0o644)
    partial.rename(destination)

def payload_offset(path):
    with path.open('rb') as stream:
        header = stream.read(1024 * 1024)
        match = re.search(rb'''(?m)^skip=['"]?(\d+)['"]?\r?$''', header)
        if not match:
            raise ValueError('NVIDIA .run payload marker missing.')
        lines = int(match.group(1))
        if not 2 <= lines <= 10000:
            raise ValueError('Implausible payload marker.')
        stream.seek(0)
        for _ in range(lines - 1):
            line = stream.readline(1024 * 1024)
            if not line.endswith(b'\n'):
                raise ValueError('Truncated installer header.')
        return stream.tell()

def safe_member_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or any(':' in part for part in path.parts):
        raise ValueError('Unsafe archive path.')
    return path

def extract_reference(archive, destination, expected_sha):
    if sha(archive) != expected_sha:
        raise ValueError('Archive hash differs; extraction refused.')
    offset = payload_offset(archive)
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    total = 0
    with archive.open('rb') as stream:
        stream.seek(offset)
        with tarfile.open(fileobj=stream, mode='r|*') as tar:
            for member in tar:
                relative = safe_member_name(member.name)
                target = destination.joinpath(*relative.parts)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                if not member.isfile():
                    rows.append({'path': member.name, 'skipped': 'link_or_special_file'})
                    continue
                total += member.size
                if member.size > 2 * 1024**3 or total > 4 * 1024**3:
                    raise ValueError('Extraction size limit exceeded.')
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output, 1024 * 1024)
                target.chmod(0o644)
                rows.append({'path': member.name, 'bytes': target.stat().st_size, 'SHA256': sha(target)})
    receipt = {'archive_SHA256': expected_sha, 'payload_offset': offset, 'installer_executed': False, 'files': rows}
    (destination / 'EXTRACTION.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--id')
    parser.add_argument('--download', action='store_true')
    parser.add_argument('--extract-from', type=Path)
    args = parser.parse_args()
    catalog = json.loads((ROOT / 'dependencies/references.json').read_text())['nvidia_linux']
    if args.list or not args.id:
        print(json.dumps(catalog, indent=2))
        if args.download or args.extract_from:
            parser.error('--id is required for retrieval/extraction.')
        return
    matches = [row for row in catalog if row['id'] == args.id]
    if len(matches) != 1:
        parser.error('Unknown reference id; use --list.')
    item = matches[0]
    if not args.download and not args.extract_from:
        parser.error('Select --download and/or --extract-from explicitly.')
    downloads = ROOT / 'downloads'
    downloads.mkdir(exist_ok=True)
    if args.download:
        target = downloads / Path(urllib.parse.urlparse(item['url']).path).name
        download_reference(item, target)
        print(json.dumps({'download': target.name, 'SHA256': sha(target), 'installed': False}))
    if args.extract_from:
        destination = downloads / 'extracted' / item['id']
        receipt = extract_reference(args.extract_from.resolve(), destination, item['SHA256'])
        print(json.dumps({'extracted': str(destination.relative_to(ROOT)), 'entries': len(receipt['files']), 'installer_executed': False}))

if __name__ == '__main__':
    main()
