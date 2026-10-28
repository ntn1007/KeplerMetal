#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck two GTX runs, the M1 reference and the separate compiler capture."""
import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

EXPERIMENT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def reverify(directory):
    with tempfile.TemporaryDirectory(prefix='kepler-divergence-audit-') as tmp:
        out=Path(tmp)/'verified.json'
        result=subprocess.run([sys.executable,str(EXPERIMENT/'verify.py'),'--report',str(directory/'report.json'),
                               '--outputs',str(directory/'outputs'),'--out',str(out)],capture_output=True,timeout=90)
        need(result.returncode==0,'raw-output verification failed')
        result=json.loads(out.read_text());prior=json.loads((directory/'verified.json').read_text())
        need(result==prior,'stored verification differs from raw outputs')
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','gtx1','gtx2','m1','capture','analysis','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required')
    build=a.build.resolve();capture=a.capture.resolve();analysis=a.analysis.resolve()
    for name in ('host.mm','shader.metal'):
        need(sha(build/name)==sha(EXPERIMENT/name),'source snapshot differs: '+name)
    records=[];intervals=[]
    for directory in (a.gtx1.resolve(),a.gtx2.resolve()):
        manifest=json.loads((directory/'manifest.json').read_text());report=json.loads((directory/'report.json').read_text())
        need(manifest['GPU_reservation']['state']=='terminal' and not manifest['SIGKILL_requested'] and
             not manifest['authoritative_ps_status'] and manifest['exit_code']==0,'GTX host unresolved')
        need(manifest['original_binary_sha256']==sha(build/'host') and
             manifest['signed_binary_sha256']==sha(directory/'application') and
             manifest['source_SHA256']['shader.metallib']==sha(build/'shader.metallib')==sha(directory/'shader.metallib') and
             all(manifest['source_SHA256'][n]==sha(build/n) for n in ('shader.metal','host.mm','shader.air')),
             'GTX input identity differs')
        signature=subprocess.run(['codesign','--verify','--strict',str(directory/'application')],capture_output=True,timeout=15)
        need(signature.returncode==0,'GTX signature differs')
        intervals.append((manifest['started_at'],manifest['completed_at']))
        verified=reverify(directory)
        need(report['device']=='NVIDIA GeForce GTX 880M' and report['registry_id']==4294968416 and
             verified['status']=='OBSERVED_MISMATCH' and verified['checked_words']==227520,
             'GTX device or scope differs')
        need(verified['totals']=={'active_expected':14226,'inactive_expected':0,'success':0,
                                  'final':0,'witness':0,'guard_bytes':0},'GTX result differs')
        for case in verified['cases']:
            expected=case['expected_active'] if case['variant']==1 else 0
            need(case['mismatches']['active_expected']==expected and
                 all(case['mismatches'][k]==0 for k in ('inactive_expected','success','final','witness','guard_bytes')),
                 'GTX mismatch distribution differs')
        records.append({'device':report['device'],'dispatches':verified['dispatches'],'checked_words':verified['checked_words'],
                        'totals':verified['totals'],'signed_host_SHA256':manifest['signed_binary_sha256'],
                        'report_SHA256':sha(directory/'report.json'),'raw_output_SHA256':[x['output_SHA256'] for x in verified['cases']]})
    intervals.sort();need(intervals[0][1]<=intervals[1][0],'GTX processes overlap')
    m1=a.m1.resolve()
    provenance=json.loads((m1/'provenance.json').read_text())
    need(provenance['architecture']=='arm64' and provenance['signature_valid'] and
         all(provenance['SHA256'][name]==sha(EXPERIMENT/name) for name in ('host.mm','shader.metal','verify.py')) and
         provenance['SHA256']['report.json']==sha(m1/'report.json') and
         provenance['SHA256']['verified.json']==sha(m1/'verified.json'), 'M1 source or signature differs')
    need(sha(m1/'report.json')=='7826ecd3bc6dd757f559186660ae8f12d4fb1127aa1fdf2354d562f07a4483df' and
         sha(m1/'verified.json')=='8bc3dc0aa1732ec16120eb876f6163ff1871b783cc6b5d3c7c5779b6468a316f',
         'transferred M1 reports differ')
    reference=reverify(m1)
    need(reference['device']=='Apple M1 Max' and reference['status']=='PASS' and reference['dispatches']==48 and
         reference['checked_words']==227520 and not any(reference['totals'].values()),'M1 reference differs')
    observation=json.loads((analysis/'analysis.json').read_text())
    capture_manifest=json.loads((capture/'manifest.json').read_text())
    need(capture_manifest['GPU_reservation']['state']=='terminal' and not capture_manifest['SIGKILL_requested'] and
         not capture_manifest['authoritative_ps_status'] and capture_manifest['exit_code']==0 and
         capture_manifest['library_SHA256']==sha(build/'shader.metallib')==observation['library_SHA256'] and
         sha(capture/'native.sass')==observation['native_SHA256'] and
         observation['decoder_reproduced_listing'] and observation['indirect_branch_offsets']==[0x290] and
         observation['flow_refusal']=={'status':'REFUSED','reason':'indirect or unsupported branch'} and
         not observation['AIR_contract']['qualified'] and not observation['certificate_authorized'],
         'compiler capture evidence differs')
    report={'status':'PASS','source_SHA256':{n:sha(EXPERIMENT/n) for n in ('host.mm','shader.metal','verify.py')},
            'gtx_runs':records,'m1':{'device':reference['device'],'dispatches':reference['dispatches'],
                  'checked_words':reference['checked_words'],'totals':reference['totals'],
                  'report_SHA256':sha(m1/'report.json'),'raw_output_SHA256':[x['output_SHA256'] for x in reference['cases']],
                  'provenance':provenance},
            'capture':observation,'m1_execution_uses_separate_GPU':True,'code_residency_readback':False,
            'performance_benchmark':False,'new_runtime_support':False}
    with out.open('x') as stream:json.dump(report,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({'status':'PASS','GTX_runs':len(records),'GTX_active_expected_mismatches_each':14226,
                      'M1_status':reference['status'],'capture_indirect_branch_offset':'0x290'}))


if __name__=='__main__':main()
