#!/usr/bin/env python3
"""Observe unchanged native CAS compiler outputs in isolated processes; no dispatch."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess
ROOT=Path(__file__).resolve().parents[1];ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();OUT=a.out.resolve();OUT.relative_to(ROOT/'results');assert not OUT.exists();OUT.mkdir(parents=True)
cases=json.loads((a.input/'results.json').read_text());commands=[];rows=[]
def run(cmd,label):
    p=subprocess.run(cmd,capture_output=True,text=True,cwd=ROOT,timeout=45);(OUT/(label+'.stdout')).write_text(p.stdout);(OUT/(label+'.stderr')).write_text(p.stderr);commands.append({'argv':cmd,'exit_code':p.returncode});assert p.returncode==0,p.stderr
for space in ['device','threadgroup']:
    c=next(r for r in cases if r['address_space']==space and r['op']=='weak' and r['local']==1 and not r.get('runtime_language'))
    capture=OUT/(space+'-capture');execution=OUT/(space+'-capture-execution')
    run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(ROOT/'build/compiler_output_trace'),'--out',str(execution),'--timeout','20','--',c['library'],str(capture),'compute','test'],space+'-capture')
    result=json.loads((execution/'execution.stdout').read_text());assert result['pipeline_created'] and result['gpu_dispatch']==False
    for index,e in enumerate(result['captures']):
        container=Path(e['file']).read_bytes();offset=8;code=None;sections=[]
        while offset+16<=len(container):
            next_offset,kind,size=struct.unpack_from('<QII',container,offset);payload=offset+16;assert size<=len(container)-payload
            sections.append({'kind':kind,'bytes':size,'offset':payload})
            if kind==0x10005:code=container[payload:payload+size]
            if not next_offset:break
            assert next_offset>=16+size and offset+next_offset<len(container)
            offset+=next_offset
        assert code is not None
        output=OUT/f'{space}-{index}.sass';output.write_bytes(code);decode=OUT/f'{space}-{index}-decode'
        run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(ROOT/'build/envydis-only/envydis/envydis'),'--out',str(decode),'--timeout','20','--','-m','gf100','-V','gk104','-i','-n',str(output)],space+'-decode')
        asm=(decode/'execution.stdout').read_text()
        rows.append({'space':space,'library':c['library'],'container_sha256':hashlib.sha256(container).hexdigest(),'code_sha256':hashlib.sha256(code).hexdigest(),'code_bytes':len(code),'sections':sections,'assembly_file':str(decode/'execution.stdout'),'gpu_dispatch':False,'native_code_unchanged':True,'decode_complete':('[unknown' not in asm),'unknown_lines':[l for l in asm.splitlines() if '[unknown' in l],'atomic_lines':[l for l in asm.splitlines() if any(s in l for s in ['atom','ld lock','st unlock'])],'scope':'Constructor input bytes only; incomplete decoder output is not instruction-level proof or a resident GPU code dump.'})
(OUT/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');(OUT/'summary.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
