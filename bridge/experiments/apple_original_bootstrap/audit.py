#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit two captured Apple Release app runs against archived GTX controls."""
import argparse, collections, datetime, hashlib, json, struct, subprocess, zipfile
from pathlib import Path

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha(p): return sha_bytes(Path(p).read_bytes())
def need(v,why):
    if not v: raise ValueError(why)
def load(p): return json.loads(Path(p).read_text())
def tree(path):
    entries=sorted(path.rglob('*')); need(not any(x.is_symlink() for x in entries),'bundle contains a symlink')
    return {str(x.relative_to(path)):sha(x) for x in entries if x.is_file()}
def sections(path):
    b=Path(path).read_bytes(); need(len(b)>=32,'Mach-O header')
    if struct.unpack_from('>I',b)[0]==0xcafebabe:
        n=struct.unpack_from('>I',b,4)[0]; need(0<n<32 and 8+20*n<=len(b),'fat header')
        arch=[struct.unpack_from('>IIIII',b,8+i*20) for i in range(n)]
        choices=[x for x in arch if x[0]==0x01000007]; need(len(choices)==1,'x86_64 slice')
        _,_,offset,size,_=choices[0]; need(offset+size<=len(b),'slice bounds'); b=b[offset:offset+size]
    magic,_,_,_,ncmds,cmdbytes,_,_=struct.unpack_from('<IiiIIIII',b); need(magic==0xfeedfacf and ncmds<1000 and 32+cmdbytes<=len(b),'64-bit Mach-O header')
    out={}; o=32
    for _ in range(ncmds):
        need(o+8<=len(b),'load command'); cmd,size=struct.unpack_from('<II',b,o); need(size>=8 and o+size<=len(b),'load command bounds')
        if cmd==0x19:
            need(size>=72,'segment size'); seg=b[o+8:o+24].rstrip(b'\0').decode('ascii'); n=struct.unpack_from('<I',b,o+64)[0]; need(72+80*n<=size,'section table')
            for j in range(n):
                t=o+72+j*80; name=b[t:t+16].rstrip(b'\0').decode('ascii'); sz=struct.unpack_from('<Q',b,t+40)[0]; off=struct.unpack_from('<I',b,t+48)[0]; flags=struct.unpack_from('<I',b,t+64)[0]
                if off and flags&0xff not in (1,12,18):
                    need(off+sz<=len(b) and (seg,name) not in out,'section bounds'); out[(seg,name)]={'size':sz,'sha256':sha_bytes(b[off:off+sz])}
        o+=size
    need(o==32+cmdbytes and ('__TEXT','__text') in out,'Mach-O command table'); return out

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('sample','release','build','direct','blank','out'): p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=2,required=True); a=p.parse_args()
    need(not a.out.exists(),'fresh audit output required'); b=load(a.build/'build.json'); need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'],'build status')
    need(tree(a.build/'Sample.app')==b['bundle_files_sha256'],'built bundle differs')
    for name,digest in b['files_sha256'].items(): need(sha(a.build/name)==digest,'built artifact differs: '+name)
    zip_path=a.sample/'AppleSample.zip'; need(sha(zip_path)==b['apple_archive_sha256']=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive')
    with zipfile.ZipFile(zip_path) as z:
        names=[n for n in z.namelist() if not n.startswith('.git/') and n.endswith(('.m','.h','.metal','.pbxproj','.plist','.storyboard'))]
        need(len(names)==17 and all((a.sample/'source'/n).is_file() and (a.sample/'source'/n).read_bytes()==z.read(n) for n in names),'sample source differs')
    original=a.release/'Contents/MacOS/Indirect Command Buffers on CPU'; signed=a.build/'application'; need(sha(original)==b['xcode_original_executable_sha256'] and sha(signed)==b['signed_executable_sha256'],'executable hashes')
    x,y=sections(original),sections(signed); need(x==y,'signed x86_64 sections differ from Xcode output')
    for file in (signed,a.build/'bootstrap.dylib'): subprocess.run(['codesign','--verify','--strict',str(file)],check=True,capture_output=True)
    imports=subprocess.run(['nm','-u',str(signed)],check=True,capture_output=True,text=True).stdout
    need('NSApplicationMain' in imports and 'KPCPUICB' not in imports and 'Kepler' not in imports,'unexpected executable imports')
    need(sha(a.release/'Contents/Resources/default.metallib')==b['release_default_library_sha256'] and b['release_default_library_sha256']!=b['files_sha256']['shader.metallib'],'different library identities')
    evidence=load(Path(__file__).resolve().parents[3]/'docs/apple-application-icb-validation.json'); expected={r['mode']:r for r in evidence['runs'] if r['mode'] in ('direct','blank')}
    controls=[]
    for path,mode in ((a.direct,'direct'),(a.blank,'blank')):
        m=load(path/'manifest.json'); r=load(path/'stdout.json'); f=(path/'outputs/frame-0.bin').read_bytes()
        known={x['manifest_sha256'] for x in evidence['runs'] if x['mode']==mode}
        need(sha(path/'manifest.json') in known and m['status']=='TERMINAL' and m['exit_code']==0 and m['mode']==mode and m['stdout_sha256']==sha(path/'stdout.json') and r['status']=='PASS' and r['actual_apple_renderer'] and r['application_modified'] and r['device']=='NVIDIA GeForce GTX 880M','archived '+mode+' provenance')
        need(len(f)==12800 and sha_bytes(f[256:-256])==expected[mode]['image_sha256'][0] and f[:256]==f[-256:]==bytes([0xa5])*256,'archived '+mode+' frame')
        controls.append(f)
    need(controls[0]!=controls[1],'blank control identical')
    counts=[(i+3 if i<8 else i*3)*12 for i in range(15)]; intervals=[]; rows=[]
    for path in a.runs:
        m=load(path/'manifest.json'); r=load(path/'report.json'); lease=m['reservation']; f=(path/'frame.bin').read_bytes()
        need(tree(path/'Sample.app')==b['bundle_files_sha256'],'run bundle differs')
        need(m['status']=='TERMINAL' and m['exit_code']==0 and m['report_sha256']==sha(path/'report.json') and m['stderr_sha256']==sha(path/'stderr.log') and m['stdout_sha256']==sha(path/'stdout.log') and m['build_sha256']==sha(a.build/'build.json') and m['host_sha256']==b['signed_executable_sha256'] and m['bootstrap_sha256']==b['files_sha256']['bootstrap.dylib'] and m['system_before']==m['system_after']==b['system'],'run provenance')
        if m.get('frame_sha256'): need(m['frame_sha256']==sha(path/'frame.bin'),'frame manifest')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and lease['lock_inherited_by_child'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id'] and not r['family_mac2'] and r['view_found'] and r['window_visible'] and r['pixel_readback'] and r['guards_intact'] and r['shader_substitution'] and r['fence_status']==4 and r['captured_command_status']==4 and r['draw_events']==1,'application result')
        events=collections.Counter(e['operation'] for e in r['events']); need(events['execute_CPU_render_ICB']==1 and events['newIndirectCommandBuffer']==1 and events['materialize_CPU_render_command']==15,'ICB events')
        e=next(e for e in r['events'] if e['operation']=='execute_CPU_render_ICB'); records=e['evidence']['sequence_records']; need(e['executed_indices']==list(range(15)) and e['evidence']['raw_records_copied']==15 and len(records)==15,'draw sequence')
        for i,entry in enumerate(records):
            x=entry['record']; need(x['name']=='apple_explicit_view' and x['library_SHA256']==b['files_sha256']['shader.metallib'] and x['manifest_SHA256']==b['files_sha256']['profiles.json'] and x['vertex_count']==counts[i] and x['base_instance']==i and x['instances']==1 and len(x['bindings'])==3,'draw record')
        need(f==controls[0] and f!=controls[1],'captured frame comparison')
        intervals.append((datetime.datetime.fromisoformat(m['started_at']),datetime.datetime.fromisoformat(m['completed_at']))); rows.append({'manifest_sha256':sha(path/'manifest.json'),'report_sha256':sha(path/'report.json'),'frame_sha256':sha_bytes(f),'frame_in_manifest':bool(m.get('frame_sha256'))})
    intervals.sort(); need(intervals[0][1]<=intervals[1][0],'processes overlap')
    out={'status':'PASS_BOUNDED_ORIGINAL_APP','runs':rows,'apple_archive_sha256':sha(zip_path),'source_files_matched_to_archive':len(names),'original_unsigned_executable_sha256':sha(original),'signed_executable_sha256':sha(signed),'matching_x86_64_sections':len(x),'default_release_metallib_sha256':b['release_default_library_sha256'],'substituted_metallib_sha256':b['files_sha256']['shader.metallib'],'manifest_sha256':b['files_sha256']['profiles.json'],'draws_per_run':15,'pixels_per_run':3072,'all_12800_bytes_equal_to_direct':True,'blank_control_differs':True,'original_app_sources_modified':False,'release_assertions_disabled':True,'process_local_injection':True,'pipeline_shader_substituted':True,'view_configuration_modified_for_capture':True,'general_support_proved':False,'transparent_system_integration':False,'performance_benchmark':False,'system_hashes_unchanged':True}
    a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps({'status':out['status'],'runs':len(rows),'pixels_per_run':out['pixels_per_run']}))
if __name__=='__main__': main()
