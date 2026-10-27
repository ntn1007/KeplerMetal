#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-check native compiler captures, the M1 reference and CPU geometry plans."""
import datetime,json,re,struct,subprocess,sys
from pathlib import Path
from partial_grid_plan import plan
from verify_partial_grid_capture import verify as verify_capture,sha,read
from verify_partial_grid_m1 import verify as verify_m1

def audit(depth,grid,m1):
    paths=[Path(depth).resolve(),Path(grid).resolve()];results=[]
    for p,wanted in zip(paths,('depth0','grid_coordinates')):
        v=verify_capture(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json')
        if v['function']!=wanted or v!=read(p/'verification.stdout') or read(p/'verification-execution.json')['exit_code']!=0 or v['unknown_annotations']:raise ValueError('Native capture or decoder incomplete')
        subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15);results.append((p,v,i,m))
    if results[0][2]['build_inputs_SHA256']!=results[1][2]['build_inputs_SHA256'] or results[0][2]['profile']!=results[1][2]['profile'] or results[0][3]['pid']==results[1][3]['pid']:raise ValueError('Different captures or process identity')
    if datetime.datetime.fromisoformat(results[0][3]['completed_at'])>=datetime.datetime.fromisoformat(results[1][3]['started_at']):raise ValueError('Native captures overlap')
    def line_map(p):
        d={}
        for line in (p/'disassembly.stdout').read_text().splitlines():
            z=re.match(r'^([0-9a-f]{8}):\s+[0-9a-f]+\s+[0-9a-f]+\s+(.*)$',line)
            if z:d[int(z.group(1),16)]=z.group(2)
        return d
    a=line_map(paths[0]);b=line_map(paths[1])
    if results[0][1]['code_SHA256']!='7090afba552f714205ff6a673d717976f5b8d58eb77f9f75b6739a2d16206f97' or results[1][1]['code_SHA256']!='82e56a5882b36b3d4ff3db4111257a605da8ca0e646660ceda506508a9ee2f56':raise ValueError('Different native programs require requalification')
    if not (re.fullmatch(r'mov b32 \$r0 \$tidx',a.get(8,'')) and re.fullmatch(r'mov b32 \$r1 \$ctaidx',a.get(16,'')) and
            re.fullmatch(r'add \$r0 \(mul s32 \$r1 s32 c1\[0x6f0\]\) \$r0',a.get(24,'')) and re.fullmatch(r'add b32 \$r0 \$r0 c1\[0x710\]',a.get(32,''))):raise ValueError('The pinned 1D coordinate dataflow differs')
    for offset,token in ((0x38,'$ctaidy'),(0x60,'$ctaidz'),(0x90,'$ctaidx'),(0xd0,'c1[0x714]'),(0xd8,'c1[0x718]'),(0xe8,'c1[0x710]'),(0x128,'c1[0x730]'),(0x118,'c1[0x734]'),(0x148,'c1[0x738]')):
        if token not in b.get(offset,''):raise ValueError('Pinned 3D instruction site differs')
    if '[[thread_position_in_grid]]' not in (paths[0]/'assets/control_flow.metal').read_text() or '[[threadgroup_position_in_grid]]' not in (paths[1]/'assets/cpu_icb_grid3d.metal').read_text():raise ValueError('Shader source attributes differ')
    m1=Path(m1).resolve();refs=[verify_m1(m1,True,c) for c in ('qualified-01','qualified-02')]
    if refs[0]['source_SHA256']!=refs[1]['source_SHA256'] or refs[0]['binary_SHA256']!=refs[1]['binary_SHA256'] or refs[0]['rows']!=refs[1]['rows']:raise ValueError('M1 reference cohorts differ')
    manifests=[read(m1/c/'manifest.json') for c in ('qualified-01','qualified-02')]
    if len({r['pid'] for m in manifests for r in m['records']})!=6 or datetime.datetime.fromisoformat(manifests[0]['records'][-1]['completed_at'])>=datetime.datetime.fromisoformat(manifests[1]['records'][0]['started_at']):raise ValueError('Reference processes overlap or repeat')
    checked=0;region_counts={}
    for cohort in ('qualified-01','qualified-02'):
        for mode,g,l in [('partial1d',(33,1,1),(32,1,1)),('partial3d',(11,7,5),(4,4,3))]:
            geometry=plan(g,l,1000);region_counts[mode]=len(geometry['segments']);raw=(m1/cohort/mode/'output.bin').read_bytes();seen=set()
            for s in geometry['segments']:
                for z in range(s['physical_group_count'][2]):
                    for y in range(s['physical_group_count'][1]):
                        for x in range(s['physical_group_count'][0]):
                            c=(x,y,z);group=tuple(b+n for b,n in zip(s['group_base'],c));local=tuple(s['actual_local'])
                            for lz in range(local[2]):
                                for ly in range(local[1]):
                                    for lx in range(local[0]):
                                        lane=(lx,ly,lz);gid=tuple(o+k*sz+u for o,k,sz,u in zip(s['thread_origin'],c,local,lane));index=gid[0]+g[0]*(gid[1]+g[1]*gid[2])
                                        if index in seen:raise ValueError('Overlapping planned logical threads')
                                        seen.add(index);r=struct.unpack_from('<32I',raw,64+index*128)
                                        if tuple(r[0:3])!=gid or tuple(r[4:7])!=lane or tuple(r[8:11])!=group or tuple(r[16:19])!=local or tuple(r[20:23])!=l or tuple(r[12:15])!=tuple(geometry['logical_group_count']) or tuple(r[24:27])!=g:raise ValueError('Reference disagrees with region plan')
                                        checked+=1
            if len(seen)!=geometry['invocations']:raise ValueError('Planner lost logical threads')
    return {'audit':'PASS','native_capture_processes':2,'native_pipeline_construction_only':True,'native_GPU_execution_proved':False,
            'current_driver_SHA256':results[0][2]['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],
            'native_code_SHA256':{x[1]['function']:x[1]['code_SHA256'] for x in results},'native_listing_SHA256':{x[1]['function']:x[1]['listing_SHA256'] for x in results},
            'native_capture_manifest_SHA256':{x[1]['function']:sha(x[0]/'execution/manifest.json') for x in results},
            'm1_reference_cohorts':2,'m1_reference_processes':6,'m1_GPU_threads':sum(x['positive_threads'] for x in refs),
            'm1_raw_uint32_checked':sum(x['uint32_values_checked'] for x in refs),'m1_negative_untouched_bytes':sum(x['rows'][0]['untouched_bytes'] for x in refs),
            'm1_reference_manifest_SHA256':[x['manifest_SHA256'] for x in refs],
            'planner_threads_cross_checked':checked,'planner_region_counts':region_counts,'planner_safe_to_dispatch':False,
            'native_origin_execution_proved':False,'partial_groups_implemented_and_qualified':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':
    if len(sys.argv)!=4:raise SystemExit('usage: audit_partial_grid_research.py DEPTH_CAPTURE GRID_CAPTURE M1_ROOT')
    print(json.dumps(audit(*sys.argv[1:]),indent=2,sort_keys=True))
