#!/usr/bin/env python3
"""Sequential GPU nonregression using rebuilt public SDK clients."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser();p.add_argument('--clients',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--resume',action='store_true')
    a=p.parse_args();clients=a.clients.resolve();clients.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results')
    if a.resume:assert out.is_dir() and (out/'commands.json').is_file()
    else:out.mkdir(exist_ok=False)
    assert json.loads((clients/'client-builds.json').read_text())['status']=='PASS'
    previous=ROOT/'results/registered-resident-sdk-extracted-20261014-02'
    old=json.loads((ROOT/'results/registered-resident-nonregression-suite-20261014/commands.json').read_text())
    commands=[]
    for c in old:
        assert c['exit_code']==0
        args=[x.replace(str(previous),str(clients)).replace('registered-resident-regression-','resident-dynamic-regression-')for x in c['argv']]
        commands.append({'label':c['label'],'argv':args})
    assert len(commands)==81
    sdk=clients/'KeplerMetalSDK'
    for variant,build,modes,verifier in [
        ('registered','registered',['prepare','chain','range','chain_completed','range_completed','no_second'],'verify_registered_resident_copy.py'),
        ('registered_bounds','registered_bounds',['prepare_short','copy_short'],'verify_registered_resident_bounds.py')]:
        for mode in modes:
            target=ROOT/'results'/('resident-dynamic-regression-'+variant+'-'+mode+'-20261014')
            args=['python3',str(ROOT/'tools/run_registered_resident_copy.py'),'--build',str(clients/(build+'-application')),'--out',str(target),'--reservation-root',str(ROOT),'--mode',mode]
            commands.extend([{'label':variant+'-'+mode,'argv':args},
                             {'label':variant+'-'+mode+'-verify','argv':['python3',str(sdk/'examples'/verifier),str(target),'--out',str(target/'independent-verification.json')]}])
    for variant in ['manifest','grid3d']:
        for mode in ['prepare','execute']:
            target=ROOT/'results'/('resident-dynamic-regression-'+variant+'-'+mode+'-20261014')
            args=['python3',str(ROOT/'tools/run_sdk_legacy_icb_probe.py'),'--build',str(clients/(variant+'-application')),'--out',str(target),'--variant',variant,'--mode',mode]
            commands.extend([{'label':variant+'-'+mode,'argv':args},
                             {'label':variant+'-'+mode+'-verify','argv':['python3',str(ROOT/'tools/verify_sdk_legacy_icb_probe.py'),'--input',str(target),'--variant',variant]}])
    assert len(commands)==105
    history=json.loads((out/'commands.json').read_text())if a.resume else []
    for c in commands:
        previous=[x for x in history if x['label']==c['label']]
        if previous and previous[-1]['exit_code']==0:
            assert previous[-1]['argv']==c['argv']
            continue
        if previous:
            # This recovery is for a failed Python entrypoint before any child
            # or result directory existed. Never restart a GPU process here.
            assert previous[-1]['exit_code']!=0
            if c['label']=='registered-prepare':
                target=Path(c['argv'][c['argv'].index('--out')+1]);assert not target.exists()
            else:
                assert c['label']=='manifest-prepare-verify'
                target=Path(c['argv'][c['argv'].index('--input')+1]);m=json.loads((target/'execution/manifest.json').read_text())
                assert m['exit_code']==0 and m['GPU_reservation']['state']=='terminal'
                old_error=(out/(c['label']+'.stderr')).read_text();assert 'FileNotFoundError' in old_error and 'execution/cpu_icb_manifest_probe' in old_error
        log_label=c['label']+('-adapter-repaired'if previous and c['label'].endswith('-verify')else'-entrypoint-repaired'if previous else '')
        r=subprocess.run(c['argv'],capture_output=True,text=True)
        (out/(log_label+'.stdout')).write_text(r.stdout);(out/(log_label+'.stderr')).write_text(r.stderr)
        history.append(dict(c,exit_code=r.returncode));(out/'commands.json').write_text(json.dumps(history,indent=2)+'\n')
        assert r.returncode==0,(c['label'],r.stderr[-2500:])
        print(c['label'],'PASS',r.stdout[-120:].replace('\n',' '),flush=True)
    (out/'completion.json').write_text(json.dumps({'status':'PASS','planned_commands':105,'attempts':len(history),'GPU_cohorts':89,'concurrent_GTX_dispatch':False,'recovered_missing_entrypoint_before_GPU':a.resume},indent=2)+'\n')


if __name__=='__main__':main()
