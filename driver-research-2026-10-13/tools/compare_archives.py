#!/usr/bin/env python3
"""Static comparison only: file hashes, readable kernel diffs and release index."""
from pathlib import Path
import datetime,difflib,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'comparison';OUT.mkdir(exist_ok=True)
VERSIONS=['355.11','418.113','450.57','470.63.01','470.256.02']
def sha(b):return hashlib.sha256(b).hexdigest()
inventories={};support=[];objects=[];index=[]
for version in VERSIONS:
    p=ROOT/'extracted'/version
    manifest=json.loads((ROOT/'extracted'/(version+'-manifest.json')).read_text())
    inventories[version]={e['path']:e for e in manifest['entries'] if e.get('sha256')}
    html=(p/'html/supportedchips.html').read_text()
    rows=[]
    for m in re.finditer(r'<tr[^>]*>.*?</tr>',html,re.S):
        cells=[re.sub('<[^>]+>',' ',s).strip() for s in re.findall(r'<td[^>]*>(.*?)</td>',m.group(),re.S)]
        if len(cells)>1 and cells[1].lower().removeprefix('0x')=='1198':rows.append(cells)
    support.append({'version':version,'exact_pci_id':'10de:1198','listed_in_package':bool(rows),'rows':rows,'source':str((p/'html/supportedchips.html').relative_to(ROOT)),'note':'Absence from this table does not prove refusal by the binary driver; no Linux execution performed.'})
    for f in p.rglob('*o_binary'):
        b=f.read_bytes();objects.append({'version':version,'file':str(f.relative_to(ROOT)),'bytes':len(b),'sha256':sha(b),'magic':b[:16].hex(),'format':'ELF64 x86_64 relocatable' if b[:5]==b'\x7fELF\x02' else 'other'})
    lines=(p/'NVIDIA_Changelog').read_text().splitlines();branch=None;entry=None
    for i,line in enumerate(lines,1):
        branch_match=re.match(r'=+ Release (\d+) Entries =+',line)
        date_match=re.match(r'(\d{4}-\d{2}-\d{2}) version ([\d.]+)',line)
        if branch_match or date_match:
            if entry:entry['end_line']=i-1;index.append(entry)
            if branch_match:branch=branch_match.group(1)
            entry={'package':version,'branch':branch,'version':date_match.group(2) if date_match else None,'date':date_match.group(1) if date_match else None,'start_line':i,'bullet_count':0,'unversioned_branch_preamble':bool(branch_match)}
        elif entry and re.match(r'    \* ',line):entry['bullet_count']+=1
    if entry:entry['end_line']=len(lines);index.append(entry)
comparisons=[]
for before,after in zip(VERSIONS,VERSIONS[1:]):
    a=inventories[before];b=inventories[after];added=sorted(set(b)-set(a));removed=sorted(set(a)-set(b));changed=sorted(n for n in set(a)&set(b) if a[n]['sha256']!=b[n]['sha256'])
    kernel=[];diffs=[]
    for n in sorted(set(a)|set(b)):
        if not n.startswith('kernel/') or n.endswith('o_binary'):continue
        if n in a and n in b and a[n]['sha256']==b[n]['sha256']:continue
        old=(ROOT/'extracted'/before/n).read_bytes() if n in a else b'';new=(ROOT/'extracted'/after/n).read_bytes() if n in b else b''
        if b'\x00' in old+new:continue
        try:x=old.decode('utf-8').splitlines(keepends=True);y=new.decode('utf-8').splitlines(keepends=True)
        except UnicodeError:continue
        delta=list(difflib.unified_diff(x,y,fromfile=before+'/'+n,tofile=after+'/'+n))
        kernel.append({'path':n,'change':'added' if n not in a else 'removed' if n not in b else 'changed','lines_added':sum(l.startswith('+') and not l.startswith('+++') for l in delta),'lines_removed':sum(l.startswith('-') and not l.startswith('---') for l in delta),'old_sha256':a.get(n,{}).get('sha256'),'new_sha256':b.get(n,{}).get('sha256')});diffs.extend(delta)
    diff_file=f'kernel-{before}-to-{after}.diff';(OUT/diff_file).write_text(''.join(diffs))
    comparisons.append({'before':before,'after':after,'added':added,'removed':removed,'changed':changed,'readable_kernel_changes':kernel,'kernel_diff_file':diff_file,'interpretation':'Static file differences only. Closed RM/modeset binaries and user-space ELF libraries are not source-level histories. No port, build or Linux execution.'})
(OUT/'package-comparison.json').write_text(json.dumps(comparisons,indent=2)+'\n')
(OUT/'support-1198.json').write_text(json.dumps(support,indent=2)+'\n')
(OUT/'closed-core-objects.json').write_text(json.dumps(objects,indent=2)+'\n')
(OUT/'changelog-index.json').write_text(json.dumps(index,indent=2)+'\n')
for c in comparisons:print(c['before'],'->',c['after'],'changed:',len(c['changed']),'added:',len(c['added']),'removed:',len(c['removed']),'readable kernel files:',len(c['readable_kernel_changes']))
print('PCI 1198:',[(r['version'],r['listed_in_package']) for r in support])
