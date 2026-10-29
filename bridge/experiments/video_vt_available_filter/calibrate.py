#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate the register observer on three bounded CPU-only cases."""
import argparse,hashlib,json,os,plistlib,re,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
NAMES=('cpu.cpp','cpu.S','lldb_witness.py','lldb_guard.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(argv,env=None):
    p=subprocess.run([str(x) for x in argv],capture_output=True,text=True,env=env,timeout=90)
    if p.returncode:raise ValueError('command failed: '+p.stderr[-1000:])
    return p.stdout
def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse',type=Path);a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    out.mkdir()
    for n in NAMES:shutil.copyfile(HERE/n,out/n)
    if a.reuse:
        source=a.reuse.resolve()
        if any(sha(source/n)!=sha(HERE/n) for n in NAMES):raise ValueError('reused sources differ')
        host=out/'host';shutil.copyfile(source/'host',host);host.chmod(0o755);run(['codesign','--verify','--strict',host])
        logs={}
        for name in ('one','zero','wrong','wrongid','null','equal','wrongkey','wrongvalue','unavailable','other','unavailableother','wrongout','wrongitem','rejectfilter'):
            shutil.copyfile(source/(name+'.log'),out/(name+'.log'));logs[name]=(out/(name+'.log')).read_text()
            if 'KP_PROCESS_EXITED' not in logs[name] or 'KM_TRACE_HIT_FAIL' in logs[name]:raise ValueError('terminal or hit differs')
    else:
        ent=out/'entitlements.plist';ent.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow':True}))
        host=out/'host';run(['xcrun','clang++','-arch','x86_64','-O0','-g','-Wall','-Wextra','-Werror',out/'cpu.cpp',out/'cpu.S','-o',host]);run(['codesign','--force','--sign','-','--entitlements',ent,host]);run(['codesign','--verify','--strict',host])
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))};env['KM_TRACE_MODE']='cpu'
        cmd=['xcrun','lldb','--no-lldbinit','--batch','-o','command script import '+json.dumps(str(out/'lldb_witness.py')),
             '-o','command script import '+json.dumps(str(out/'lldb_guard.py')),
             '-o','breakpoint set -H -K false -n KMTraceReady','-o','breakpoint command add -F lldb_witness.arm 1',
             '-o','run','-o','script lldb_guard.await_terminal(lldb.debugger)','-o','quit','--',host]
        logs={}
        for name,args in [('one',['1']),('zero',['0']),('wrong',['1','wrong']),('wrongid',['1','wrongid']),('null',['1','null']),('equal',['1','equal']),('wrongkey',['1','wrongkey']),('wrongvalue',['1','wrongvalue']),('unavailable',['1','unavailable']),('other',['1','other']),('unavailableother',['1','unavailableother']),('wrongout',['1','wrongout']),('wrongitem',['1','wrongitem']),('rejectfilter',['1','rejectfilter'])]:
            log=run(cmd+args,env);(out/(name+'.log')).write_text(log);logs[name]=log
            if 'KP_PROCESS_EXITED' not in log or 'KM_TRACE_HIT_FAIL' in log:raise ValueError('terminal or hit differs')
    for name,count,match in [('one',1,1),('zero',0,1),('wrongid',1,0),('null',1,1),('equal',1,1),('wrongkey',1,1),('wrongvalue',1,1),('unavailable',1,1),('other',1,1),('unavailableother',1,1),('wrongout',1,1),('wrongitem',1,1),('rejectfilter',1,1)]:
        log=logs[name]
        devices=re.findall(r'^KM_TRACE_DEVICE thread=(\d+) target_match='+str(match)+r' bytes_match=1$',log,re.M)
        lists=re.findall(r'^KM_TRACE_LIST thread=(\d+) nonnull=1 bytes_match=1$',log,re.M)
        items=str(match) if count else '-1'
        batches=re.findall(r'^KM_TRACE_BATCH thread=(\d+) count='+str(count)+r' same_list=1 item_match='+items+r' bytes_match=1$',log,re.M)
        input_hits=re.findall(r'^KM_TRACE_FILTER_INPUT thread=(\d+) device_match='+str(match)+r' bytes_match=1$',log,re.M)
        alloc_hits=re.findall(r'^KM_TRACE_DICT_ALLOC thread=(\d+) nonnull='+str(0 if name=='null' else 1)+r' bytes_match=1$',log,re.M)
        output_hits=re.findall(r'^KM_TRACE_FILTER_OUTPUT thread=(\d+) input_match='+str(match)+r' nonnull='+str(0 if name=='null' else 1)+r' same_alloc=1 bytes_match=1$',log,re.M)
        if count and (input_hits!=lists or alloc_hits!=lists or output_hits!=lists):raise ValueError(name+' filter differs')
        if not count and (input_hits or alloc_hits or output_hits):raise ValueError(name+' unexpected filter')
        reg_hits=re.findall(r'^KM_TRACE_KEY_REG thread=(\d+) nonnull=1 same_dict=1 bytes_match=1$',log,re.M)
        name_hits=re.findall(r'^KM_TRACE_KEY_NAME thread=(\d+) nonnull=1 same_dict=1 bytes_match=1$',log,re.M)
        compare_in=re.findall(r'^KM_TRACE_COMPARE_INPUT thread=(\d+) name_match=1 key_match=1 bytes_match=1$',log,re.M)
        compare_out=re.findall(r'^KM_TRACE_COMPARE_RESULT thread=(\d+) same_input=1 equal='+str(1 if name=='equal' else 0)+r' bytes_match=1$',log,re.M)
        if count and name!='null' and (reg_hits!=lists or name_hits!=lists or compare_in!=lists or compare_out!=lists):raise ValueError(name+' keys differ')
        if (not count or name=='null') and (reg_hits or name_hits or compare_in or compare_out):raise ValueError(name+' unexpected keys')
        key_match=0 if name=='wrongkey' else 1;value_match=0 if name=='wrongvalue' else 1
        set_hits=re.findall(r'^KM_TRACE_SET_INPUT thread=(\d+) distinct_destination=1 key_match='+str(key_match)+r' value_match='+str(value_match)+r' bytes_match=1$',log,re.M)
        set_returns=re.findall(r'^KM_TRACE_SET_RETURN thread=(\d+) input_match='+str(int(bool(key_match and value_match)))+r' bytes_match=1$',log,re.M)
        if count and name!='null' and (set_hits!=lists or set_returns!=lists):raise ValueError(name+' registration differs')
        if (not count or name=='null') and (set_hits or set_returns):raise ValueError(name+' unexpected registration')
        next_hits=re.findall(r'^KM_TRACE_NEXT_BATCH thread=(\d+) count=0 same_list=1 bytes_match=1$',log,re.M)
        branch_hits=re.findall(r'^KM_TRACE_BRANCH thread=(\d+) flag='+str(1 if name=='equal' else 0)+r' same_compare=1 bytes_match=1$',log,re.M)
        path_hits=re.findall(r'^KM_TRACE_PATH thread=(\d+) choice='+('nonzero' if name=='equal' else 'zero')+r' bytes_match=1$',log,re.M)
        if count and name!='null' and (next_hits!=lists or branch_hits!=lists or path_hits!=lists):raise ValueError(name+' branch differs')
        if (not count or name=='null') and (next_hits or branch_hits or path_hits):raise ValueError(name+' unexpected branch')
        apply_hits=re.findall(r'^KM_TRACE_APPLY thread=(\d+) dest_callback_context_match=1 bytes_match=1$',log,re.M)
        callback_hits=re.findall(r'^KM_TRACE_CALLBACK thread=(\d+) key_match='+str(key_match)+r' value_match='+str(value_match)+r' context_match=1 bytes_match=1$',log,re.M)
        avail=0 if name in ('unavailable','unavailableother') else 1
        avail_hits=re.findall(r'^KM_TRACE_AVAILABLE thread=(\d+) value='+str(avail)+r' bytes_match=1$',log,re.M)
        append_hits=re.findall(r'^KM_TRACE_APPEND_INPUT thread=(\d+) context_value_match=1 bytes_match=1$',log,re.M)
        append_returns=re.findall(r'^KM_TRACE_APPEND_RETURN thread=(\d+) available=1 bytes_match=1$',log,re.M)
        if count and name!='null':
            if apply_hits!=lists or callback_hits!=lists:raise ValueError(name+' apply or callback differs')
            if key_match and value_match:
                if avail_hits!=lists or (avail and (append_hits!=lists or append_returns!=lists)) or (not avail and (append_hits or append_returns)):raise ValueError(name+' availability differs')
            elif avail_hits or append_hits or append_returns:raise ValueError(name+' wrong-entry observation')
        elif apply_hits or callback_hits or avail_hits or append_hits or append_returns:raise ValueError(name+' unexpected apply')
        expected=0 if name=='wrongout' else 1
        stores=re.findall(r'^KM_TRACE_OUT_STORE thread=(\d+) same_frame=1 same_array='+str(expected)+r' slot_nonnull=1 bytes_match=1$',log,re.M)
        outputs=re.findall(r'^KM_TRACE_OUT_AFTER thread=(\d+) same_frame=1 stored_array_match='+str(expected)+r' status=0 parent_image=host parent_offset=\d+ bytes_match=1$',log,re.M)
        qualifies=count and name not in ('null','wrongkey','wrongvalue','unavailable','unavailableother')
        if qualifies and (stores!=lists or outputs!=lists):raise ValueError(name+' output observation differs')
        if not qualifies and (stores or outputs):raise ValueError(name+' unexpected output observation')
        positive=qualifies and name!='wrongout'
        count_in=re.findall(r'^KM_TRACE_COUNT_INPUT thread=(\d+) same_array=1 same_caller_frame=1 bytes_match=1$',log,re.M)
        count_out=re.findall(r'^KM_TRACE_COUNT_OUTPUT thread=(\d+) count=1 same_caller_frame=1 bytes_match=1$',log,re.M)
        item_in=re.findall(r'^KM_TRACE_ITEM_INPUT thread=(\d+) same_array=1 index=0 same_caller_frame=1 bytes_match=1$',log,re.M)
        match=0 if name=='wrongitem' else 1
        item_out=re.findall(r'^KM_TRACE_ITEM_OUTPUT thread=(\d+) gtx_entry_match='+str(match)+r' same_caller_frame=1 bytes_match=1$',log,re.M)
        request_in=re.findall(r'^KM_TRACE_REQUEST_INPUT thread=(\d+) item_match=1 gtx_entry_match='+str(match)+r' request_nonnull=1 third_zero=1 same_caller_frame=1 bytes_match=1$',log,re.M)
        result=0 if name=='rejectfilter' else 1
        request_out=re.findall(r'^KM_TRACE_REQUEST_OUTPUT thread=(\d+) input_matched=1 return_byte='+str(result)+r' same_caller_frame=1 bytes_match=1$',log,re.M)
        if positive and any(hits!=lists for hits in (count_in,count_out,item_in,item_out,request_in,request_out)):raise ValueError(name+' request filter observation differs')
        if not positive and any((count_in,count_out,item_in,item_out,request_in,request_out)):raise ValueError(name+' unexpected request filter')
        if name=='unavailableother' and ('KM_TRACE_APPEND_OTHER_INPUT' not in log or 'KM_TRACE_APPEND_OTHER_RETURN' not in log):raise ValueError('other append not distinguished')
        if name=='other' and ('KM_TRACE_APPEND_OTHER_INPUT' in log or 'KM_TRACE_APPEND_OTHER_RETURN' in log):raise ValueError('matched breakpoints not retired')
        if log.count('KM_TRACE_ARM_PASS mode=cpu')!=1 or len(devices)!=1 or devices!=lists or batches!=lists or 'KM_TRACE_ARM_FAIL' in log:raise ValueError(name+' differs')
    if logs['wrong'].count('KM_TRACE_ARM_FAIL marker')!=1 or 'KM_TRACE_DEVICE' in logs['wrong'] or 'KM_TRACE_LIST' in logs['wrong']:raise ValueError('wrong marker differs')
    record={'status':'PASS_CPU_ENUMERATION_WITNESS','cpu_only':True,'one_and_zero_verified':True,'wrong_marker_refused':True,'wrong_target_rejected':True,'null_result_verified':True,'allocation_identity_verified':True,'equal_and_different_verified':True,'both_branch_paths_verified':True,'wrong_key_and_value_verified':True,'available_and_unavailable_verified':True,'other_entry_not_attributed':True,'wrong_output_rejected':True,'wrong_item_and_filter_rejection_verified':True,'logs_reused':bool(a.reuse),'calibrator_sha256':sha(Path(__file__)),
            'sources':{n:sha(out/n) for n in NAMES},'host_sha256':sha(host),'logs':{n:sha(out/(n+'.log')) for n in logs}}
    (out/'calibration.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n');print(json.dumps(record))
if __name__=='__main__':main()
