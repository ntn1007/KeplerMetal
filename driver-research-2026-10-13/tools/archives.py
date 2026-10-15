#!/usr/bin/env python3
"""Download NVIDIA packages and unpack tar payloads; never execute the .run shell."""
import argparse, datetime, hashlib, json, lzma, pathlib, re, shutil, tarfile, urllib.request, urllib.error
ROOT=pathlib.Path(__file__).resolve().parents[1]
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def fetch(url,p):
    partial=p.with_suffix(p.suffix+'.partial')
    with urllib.request.urlopen(url,timeout=60) as r, partial.open('wb') as f:
        shutil.copyfileobj(r,f,1024*1024)
    partial.replace(p)
    p.chmod(0o644)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--versions',nargs='+',default=['355.11','418.113','450.57','470.63.01','470.256.02']);args=ap.parse_args()
    (ROOT/'archives').mkdir(exist_ok=True);(ROOT/'extracted').mkdir(exist_ok=True)
    rows=[]
    for version in args.versions:
        assert re.fullmatch(r'\d+\.\d+(?:\.\d+)?',version)
        name=f'NVIDIA-Linux-x86_64-{version}.run';url=f'https://download.nvidia.com/XFree86/Linux-x86_64/{version}/{name}'
        p=ROOT/'archives'/name;check=ROOT/'archives'/(name+'.sha256sum')
        expected=None
        if not check.exists():
            try:fetch(url+'.sha256sum',check)
            except urllib.error.HTTPError as e:
                if e.code!=404:raise
                try:fetch(url+'.sha256',check)
                except urllib.error.HTTPError as e2:
                    if e2.code!=404:raise
        if check.exists():
            expected=check.read_text().split()[0];assert re.fullmatch('[a-fA-F0-9]{64}',expected)
        if not p.exists():
            existing=ROOT.parents[1]/'opencl-880m/drivers/linux'/name
            if existing.is_file() and expected and sha(existing)==expected:shutil.copyfile(existing,p);print('Copied previously downloaded official archive:',version,flush=True)
            else:print('Downloading:',version,flush=True);fetch(url,p)
        actual=sha(p)
        if expected:assert actual.lower()==expected.lower(),f'SHA256 mismatch: {version}'
        p.chmod(0o644)
        out=ROOT/'extracted'/version;manifest_path=ROOT/'extracted'/(version+'-manifest.json')
        if manifest_path.exists():
            previous=json.loads(manifest_path.read_text());assert previous['archive_sha256']==actual
            rows.append(previous);continue
        with p.open('rb') as f:header=f.read(200000)
        m=re.search(rb'^skip=(\d+)\r?$',header,re.M);assert m,'No makeself skip marker'
        skip=int(m.group(1));entries=[];out.mkdir(exist_ok=True)
        embedded_md5=re.search(rb'^MD5=[\"\x27]?([a-fA-F0-9]{32})',header,re.M)
        with p.open('rb') as f:
            for _ in range(skip-1):f.readline()
            offset=f.tell();assert f.read(6)==b'\xfd7zXZ\x00','Expected XZ payload';f.seek(offset)
            payload_md5=hashlib.md5()
            for chunk in iter(lambda:f.read(1024*1024),b''):payload_md5.update(chunk)
            # NVIDIA's makeself header specifies MD5 over tail -n +4, not just XZ.
            f.seek(0)
            for _ in range(3):f.readline()
            embedded_scope_md5=hashlib.md5()
            for chunk in iter(lambda:f.read(1024*1024),b''):embedded_scope_md5.update(chunk)
            if embedded_md5:assert embedded_scope_md5.hexdigest()==embedded_md5.group(1).decode().lower(),'Embedded archive MD5 mismatch'
            f.seek(offset)
            with tarfile.open(fileobj=lzma.LZMAFile(f),mode='r|') as archive:
                for member in archive:
                    path=pathlib.PurePosixPath(member.name)
                    assert not path.is_absolute() and '..' not in path.parts,member.name
                    destination=out.joinpath(*path.parts)
                    row={'path':str(path),'bytes':member.size,'tar_type':member.type.decode('ascii',errors='replace')}
                    if member.isfile():
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        h=hashlib.sha256()
                        with archive.extractfile(member) as src,destination.open('wb') as dst:
                            for chunk in iter(lambda:src.read(1024*1024),b''):dst.write(chunk);h.update(chunk)
                        destination.chmod(0o644);row['sha256']=h.hexdigest();row['extracted']=True
                    elif member.isdir():destination.mkdir(parents=True,exist_ok=True);row['extracted']=True
                    else:row.update(extracted=False,link_target=member.linkname,reason='Links and special files recorded only; no archive-controlled filesystem links created')
                    entries.append(row)
        record={'version':version,'url':url,'archive_file':str(p.relative_to(ROOT)),'archive_sha256':actual,'official_sha256_file':str(check.relative_to(ROOT)) if expected else None,'official_sha256_verified':bool(expected),'embedded_archive_md5_verified':bool(embedded_md5),'embedded_md5_scope':'Bytes from line 4 to EOF, as specified by the header','embedded_md5':embedded_scope_md5.hexdigest(),'payload_md5':payload_md5.hexdigest(),'bytes':p.stat().st_size,'payload_offset':offset,'skip_line':skip,'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'extraction':'All regular files and directories. Links/special entries retained in manifest only. Files mode 0644. Installer never executed.','entries':entries}
        manifest_path.write_text(json.dumps(record,indent=2)+'\n');rows.append(record)
        print('Extracted',version,len(entries),'entries; SHA256',actual,flush=True)
    (ROOT/'archives/manifest.json').write_text(json.dumps([{k:v for k,v in r.items() if k!='entries'} for r in rows],indent=2)+'\n')
if __name__=='__main__':main()
