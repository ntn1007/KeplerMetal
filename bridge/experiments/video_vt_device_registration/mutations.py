#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject altered evidence without running the target or modifying originals."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser()
    for n in ('build','calibration','cache','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=8,required=True);a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():raise ValueError('fresh output required')
    indices=[i for i,p in enumerate(a.runs) if json.loads((p/'manifest.json').read_text())['status']=='TERMINAL_DEBUGGER' and json.loads((p/'manifest.json').read_text())['mode']=='hardware']
    if len(indices)!=2:raise ValueError('hardware debug cohort differs')
    index=indices[0];src=a.runs[index];names=('client','manifest.json','stdout.json','stderr.log','lldb.log');before={n:sha(src/n) for n in names};a.out.mkdir();checks=[]
    for case in ('item','device','set-key','set-value','set-return','compare-result','next','branch'):
        d=a.out/case;d.mkdir();(d/'client').symlink_to((src/'client').resolve())
        for n in ('manifest.json','stdout.json','stderr.log','lldb.log'):shutil.copyfile(src/n,d/n)
        m=json.loads((d/'manifest.json').read_text())
        if case in ('item','device','set-key','set-value','set-return','compare-result','next','branch'):
            log=(d/'lldb.log').read_text()
            if case=='batch':old,new,expected='count=1 same_list=1','count=0 same_list=1','video enumeration identity differs'
            elif case=='identity':old,new,expected='count=1 same_list=1','count=1 same_list=0','video enumeration identity differs'
            elif case=='item':old,new,expected='item_match=1','item_match=0','video enumeration identity differs'
            elif case=='helper-input':old,new,expected='device_match=1','device_match=0','dictionary identity differs'
            elif case=='helper-output':old,new,expected='input_match=1 nonnull=1','input_match=1 nonnull=0','dictionary identity differs'
            elif case=='allocation':old,new,expected='KM_TRACE_DICT_ALLOC thread=','KM_TRACE_DICT_FAILED thread=','dictionary identity differs'
            elif case=='allocation-identity':old,new,expected='same_alloc=1','same_alloc=0','dictionary identity differs'
            elif case=='key-reg':old,new,expected='KM_TRACE_KEY_REG thread=','KM_TRACE_REG_FAILED thread=','key comparison differs'
            elif case=='key-name':old,new,expected='KM_TRACE_KEY_NAME thread=','KM_TRACE_NAME_FAILED thread=','key comparison differs'
            elif case=='compare-input':old,new,expected='name_match=1 key_match=1','name_match=0 key_match=1','key comparison differs'
            elif case=='compare-result':old,new,expected='same_input=1 equal=0','same_input=1 equal=1','key comparison differs'
            elif case=='next':old,new,expected='count=0 same_list=1','count=1 same_list=1','enumeration decision differs'
            elif case=='same-list':old,new,expected='count=0 same_list=1','count=0 same_list=0','enumeration decision differs'
            elif case=='branch':old,new,expected='flag=0 same_compare=1','flag=1 same_compare=1','enumeration decision differs'
            elif case=='path':old,new,expected='choice=zero','choice=nonzero','enumeration decision differs'
            elif case=='set-key':old,new,expected='distinct_destination=1 key_match=1','distinct_destination=1 key_match=0','registration call observation differs'
            elif case=='set-value':old,new,expected='key_match=1 value_match=1','key_match=1 value_match=0','registration call observation differs'
            elif case=='set-return':old,new,expected='KM_TRACE_SET_RETURN thread=','KM_TRACE_SET_MISSING thread=','registration call observation differs'
            elif case=='device':old,new,expected='target_match=1','target_match=0','video enumeration identity differs'
            else:old,new,expected='KM_TRACE_ARM_PASS mode=video','KM_TRACE_ARM_FAIL mode=video','debug receipt differs'
            if log.count(old)!=1:raise ValueError('source log differs')
            (d/'lldb.log').write_text(log.replace(old,new,1));m['lldb_log_sha256']=sha(d/'lldb.log')
        elif case=='diagnostic':
            (d/'stderr.log').write_text((d/'stderr.log').read_text()+'unexpected\n');m['stderr_sha256']=sha(d/'stderr.log');expected='video diagnostic differs'
        else:
            x=json.loads((d/'stdout.json').read_text());x['frames']=1;(d/'stdout.json').write_text(json.dumps(x)+'\n');m['stdout_sha256']=sha(d/'stdout.json');expected='hardware result differs'
        (d/'manifest.json').write_text(json.dumps(m)+'\n');runs=list(a.runs);runs[index]=d
        cmd=['python3',str(HERE/'audit.py'),'--build',str(a.build),'--calibration',str(a.calibration),'--cache',str(a.cache),'--runs',*(str(x) for x in runs),'--out',str(d/'unexpected.json')]
        result=subprocess.run(cmd,capture_output=True,text=True,timeout=120)
        if result.returncode==0 or expected not in result.stderr or (d/'unexpected.json').exists():raise ValueError(case+' not rejected for expected reason')
        checks.append({'case':case,'rejected':True,'reason':expected})
    if before!={n:sha(src/n) for n in names}:raise ValueError('originals changed')
    result={'status':'PASS_MUTATIONS_REJECTED','checks':checks,'gpu_execution':False,'originals_modified':False,'source_sha256':sha(Path(__file__)),'audit_sha256':sha(HERE/'audit.py')}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':result['status'],'checks':len(checks)}))
if __name__=='__main__':main()
