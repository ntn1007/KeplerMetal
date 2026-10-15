#!/usr/bin/env python3
"""Read-only cross-check of loaded method identity against on-disk x86 code.
Uses the observed IMP offsets and checks LC_UUID before reading code.
"""
from pathlib import Path
import argparse,hashlib,json,re,shutil,struct,subprocess
p=argparse.ArgumentParser();p.add_argument('--inspection',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
ROOT=Path(__file__).resolve().parents[1];out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
rows=json.loads((a.inspection/'methods.json').read_text())['methods'];image=Path('/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib');data=image.read_bytes()
assert data[:4]==b'\xcf\xfa\xed\xfe' and struct.unpack_from('<I',data,4)[0]==0x01000007
ncmd=struct.unpack_from('<I',data,16)[0];offset=32;uuid=None;segments=[]
for i in range(ncmd):
 kind,size=struct.unpack_from('<II',data,offset);assert size>=8 and offset+size<=len(data)
 if kind==0x1b:uuid=data[offset+8:offset+24].hex()
 if kind==0x19:
  name=data[offset+8:offset+24].split(b'\0')[0].decode();va,vs,fo,fs=struct.unpack_from('<4Q',data,offset+24);segments.append((name,va,vs,fo,fs))
 offset+=size
text=next(s for s in segments if s[0]=='__TEXT');assert text[1]==0
checks=[];commands=[]
for row in rows:
 if row.get('image')!=str(image):continue
 assert row['image_UUID']==uuid, 'Different on-disk image from observed runtime IMP'
 va=int(row['image_offset'],16);assert text[1]<=va and va+6<=text[1]+text[4]
 fo=text[3]+va-text[1];prefix=data[fo:fo+6];slug=re.sub('[^a-zA-Z0-9]+','-',row['selector'])
 cmd=['xcrun','llvm-objdump','-d','--start-address='+hex(va),'--stop-address='+hex(va+6),str(image)]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=20);assert r.returncode==0
 file=out/(slug+'.asm');file.write_text(r.stdout);commands.append(cmd)
 checks.append({'selector':row['selector'],'owner':row['defining_class'],'observed_offset':row['image_offset'],
                'same_image_UUID':True,'prefix':prefix.hex(),'six_byte_noop':prefix==bytes.fromhex('554889e55dc3'),
                'disassembly':str(file),'disassembly_sha256':sha(file)})
assert sum(c['six_byte_noop'] for c in checks)==5
shutil.copyfile(Path(__file__),out/Path(__file__).name)
summary={'status':'PASS','image_path':str(image),'image_sha256':sha(image),'image_UUID':uuid,
         'methods_sha256':sha(a.inspection/'methods.json'),'checks':checks,'commands':commands,'GPU_dispatch':False,
         'scope':'Five inherited compute/blit ICB methods are no-ops in the UUID-matched image. Render execution and complete native ICB contract not established.'}
(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
