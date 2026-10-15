#!/usr/bin/env python3
"""Serialize the native control baseline, then preserving imports and dispatch controls."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);p.add_argument('--modes',nargs='+');a=p.parse_args()
    out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);build=a.build.resolve();history=[]
    modes=['depth'+str(n)for n in [0,4,8,16,24,40,64,96]]+['nak:depth'+str(n)for n in [0,4,8,16,24,40]]+['no_dispatch:depth0','no_dispatch:depth96','nak:no_dispatch:depth8','nak:no_dispatch:depth40']
    full=list(modes)
    if a.modes:
        assert set(a.modes)<=set(full)and len(a.modes)==len(set(a.modes));modes=a.modes
    for mode in modes:
        target=ROOT/'results'/(a.prefix+'-'+mode.replace(':','-'))
        phases=[('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',build,'--out',target,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools/verify_control_flow.py',target])]
        for phase,cmd in phases:
            cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True);label=mode.replace(':','-')+'-'+phase
            (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);history.append({'mode':mode,'phase':phase,'result':str(target),'argv':cmd,'exit_code':r.returncode});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
            if r.returncode:
                (out/'status.json').write_text(json.dumps({'status':'FAIL','mode':mode,'phase':phase,'retry':False})+'\n');print(mode,phase,r.stdout,r.stderr,flush=True);raise SystemExit(r.returncode)
        print(mode,'GPU+CPU PASS',flush=True)
    positive=12*sum('no_dispatch:'not in x for x in modes);negative=12*sum('no_dispatch:'in x for x in modes)
    (out/'status.json').write_text(json.dumps({'status':'PASS','cohorts':len(modes),'positive_trials':positive,'negative_trials':negative,'full_standard_matrix':modes==full,'full_objective_complete':False},indent=2)+'\n')
if __name__=='__main__':main()
