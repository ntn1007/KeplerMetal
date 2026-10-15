#!/usr/bin/env python3
"""Observe unmodified native compiler allocations; no GPU dispatch or import."""
from pathlib import Path
import argparse,hashlib,json,re,struct,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--depths',type=int,nargs='+');a=p.parse_args()
    build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    inp=json.loads((build/'inputs.json').read_text());assert sha(build/'compiler_output_trace')==inp['capture_executable_SHA256']
    for n,h in inp['source_hashes'].items():assert sha(build/n)==h
    for n,h in inp['assets_SHA256'].items():assert sha(build/'assets'/n)==h
    driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');assert sha(driver)=='2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054'
    commands=[];records=[]
    depths=a.depths or inp['depths'];assert set(depths)<=set(inp['depths'])and len(set(depths))==len(depths)
    for depth in depths:
        name='depth'+str(depth);case=out/name;case.mkdir();capture=case/'capture';capture.mkdir()
        cmd=list(map(str,[sys.executable,ROOT/'tools/run_signed_probe.py','--exe',build/'compiler_output_trace','--out',case/'execution','--timeout',45,'--',build/'assets/control_flow.metallib',capture,'compute',name]))
        r=subprocess.run(cmd,capture_output=True,text=True);(case/'launcher.stdout').write_text(r.stdout);(case/'launcher.stderr').write_text(r.stderr);commands.append({'label':name,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        assert not r.returncode,(name,r.stdout,r.stderr)
        m=json.loads((case/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
        d=json.loads((case/'execution/execution.stdout').read_text());assert d['pipeline_created']and not d['gpu_dispatch']and len(d['captures'])==1
        row=d['captures'][0];payload=Path(row['file']);blob=payload.read_bytes();version,total=struct.unpack_from('<2I',blob);assert version in[7,8,9]and total==len(blob)
        offset=8;words=None;code=None
        for _ in range(32):
            next_,kind,size=struct.unpack_from('<QII',blob,offset);assert offset+16+size<=len(blob)
            if kind==0x10004:assert words is None and size==232;words=list(struct.unpack_from('<58I',blob,offset+16))
            if kind==0x10005:assert code is None;code=blob[offset+16:offset+16+size]
            if not next_:break
            assert next_>=16+size;offset+=next_
        assert words is not None and code and len(code)%64==0 and row['variant_saved']
        code_file=capture/'native.sass';code_file.write_bytes(code);variant=Path(row['variant_file']);raw=variant.read_bytes()
        cmd=list(map(str,[ROOT/'build/envydis-only/envydis/envydis','-m','gf100','-V','gk104','-i','-n',code_file]));decoded=subprocess.run(cmd,capture_output=True,text=True,timeout=20);assert not decoded.returncode
        (capture/'native.envydis.txt').write_text(decoded.stdout)
        lines=[line for line in decoded.stdout.splitlines()if re.search(r'\b(joinat|join|prebreak|precont|break|brk|call|ret|cont|ssy|pbk|pcnt)\b',line)]
        item={'function':name,'source_depth':depth,'compiler_output_SHA256':sha(payload),'metadata_words':words,'code_bytes':len(code),'code_SHA256':sha(code_file),'listing_SHA256':sha(capture/'native.envydis.txt'),'variant_SHA256':sha(variant),
              'variant_words_0_128':list(struct.unpack_from('<32I',raw)),
              'control_instruction_lines':lines,'unknown_annotations':decoded.stdout.count('[unknown'),'PID':m['pid'],'GPU_dispatch':False}
        records.append(item);(out/'observations.json').write_text(json.dumps({'records':records,'driver_SHA256':sha(driver),'native_build_inputs_SHA256':sha(build/'inputs.json'),'system_modified':False},indent=2)+'\n')
        print(name,json.dumps({'GPR':words[7],'words9_14':words[9:15],'variant40_56':list(struct.unpack_from('<5I',raw,40)),'control_instructions':len(lines)}),flush=True)
    (out/'status.json').write_text(json.dumps({'status':'PASS','functions':len(records),'GPU_dispatch':False})+'\n')

if __name__=='__main__':main()
