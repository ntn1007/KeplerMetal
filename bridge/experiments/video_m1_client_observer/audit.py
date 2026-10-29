#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently check two retained public VideoToolbox reference cohorts."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from run import REFERENCE, SOURCES, TAGS

HERE=Path(__file__).resolve().parent
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,why):
    if not ok: raise ValueError(why)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--runs',type=Path,nargs=2,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    reference=a.reference.read_bytes(); need(len(reference)==691200 and sha(a.reference)==REFERENCE,'reference differs')
    results=[]
    for path in a.runs:
        summary=json.loads((path/'validation.json').read_text())
        reservation=json.loads((path/'reservation.json').read_text())
        need(summary['status']=='PASS_REFERENCE_COHORT' and summary['architecture']=='arm64' and
            summary['cohort_exit_code']==0 and summary['reservation_id']==reservation['reservation_id'] and
            reservation['state']=='terminal' and reservation['exit_code']==0 and
            not reservation['SIGKILL_requested'] and not reservation['authoritative_ps_status'],'cohort not terminal')
        need(summary['source_sha256']=={n:sha(HERE/n) for n in SOURCES} and
             summary['runner_sha256']==sha(HERE/'run.py'),'source differs')
        need(summary['reference_sha256']==REFERENCE and [r['tag'] for r in summary['runs']]==list(TAGS),'input/order differs')
        for binary,digest in summary['signed_binary_sha256'].items():
            need(sha(path/binary)==digest,'retrieved signed binary differs')
            check=subprocess.run(['codesign','--verify','--strict',str(path/binary)],capture_output=True,timeout=30)
            need(check.returncode==0,'retrieved signature verification failed')
        for row in summary['runs']:
            tag=row['tag']; raw=json.loads((path/(tag+'.json')).read_text()); data=(path/(tag+'.nv12')).read_bytes()
            need(raw['status']=='PASS' and raw['decode_statuses']==[0]*6 and raw['frames']==6 and
                 raw['bytes']==len(reference) and data==reference and sha(path/(tag+'.nv12'))==row['output_sha256'] and
                 row['differing_bytes']==0 and not (path/(tag+'.stderr')).read_bytes(),'decoded bytes differ')
            observed=tag.endswith('observed'); hardware=tag.startswith('hardware')
            need(raw['observer_loaded']==observed and raw['observer_calibrated']==observed and
                 raw['observer_loaded']==row['observer_loaded'] and raw['observer_calibrated']==row['observer_calibrated'],
                 'observer calibration differs')
            need(raw['hardware_property']==row['hardware_property'] and raw['hardware_property_status']==row['hardware_property_status'],
                 'property differs')
            if hardware: need(raw['hardware_property_status']==0 and raw['hardware_property']==1,'hardware property unavailable')
            else: need(raw['hardware_property_status']==-12900 and raw['hardware_property'] is None,'software property differs')
            need(raw['observed_counts']==row['observed_counts'] and raw['services']==row['services'] and
                 raw['detail_events']==row['detail_events'] and raw['dropped_events']==row['dropped_events']==0,
                 'observed details differ')
            if observed:
                need(len(raw['detail_events'])==sum(raw['observed_counts'][1:]),'event count differs')
                for event in raw['detail_events']:
                    need(event['service'] is None or 0<=event['service']<len(raw['services']),'service index differs')
                classes=[s['class'] for s in raw['services']]
                need('IOSurfaceRoot' in classes,'IOSurface service missing')
                agx=[i for i,s in enumerate(raw['services']) if s['class']=='AGXAcceleratorG13X']
                if hardware:
                    need(len(agx)==1 and raw['services'][agx[0]]['type']==1048581,'AGX service differs')
                    actual=[(e['kind'],e['selector']) for e in raw['detail_events'] if e['service']==agx[0]]
                    need(len(actual)==6 and set(actual)=={(2,0),(2,2),(2,5),(2,256),(2,258),(1,9)},'AGX observed calls differ')
                else: need(not agx,'software AGX observation differs')
        results.append({'cohort_receipt_sha256':sha(path/'validation.json'),'reference_macos_version':summary['macos_version'],
                        'signed_binary_sha256':summary['signed_binary_sha256'],'reservation_id':summary['reservation_id']})
    need(results[0]['reservation_id']!=results[1]['reservation_id'],'duplicate reservation')
    record={'status':'PASS_TWO_REFERENCE_COHORTS','cohorts':results,'processes':8,'hardware_processes':4,
        'observed_processes':4,'frames':48,'bytes_compared':48*115200,'differing_bytes':0,
        'hardware_sessions_report_acceleration':4,'software_property_status':-12900,
        'observed_agx_processes':2,'observed_software_agx_processes':0,
        'reference_sha256':REFERENCE,'source_sha256':{n:sha(HERE/n) for n in (*SOURCES,'run.py','audit.py')},
        'observation_is_process_local':True,'returned_port_name_correlation_only':True,
        'other_processes_observed':False,'agx_selector_semantics_qualified':False,
        'nvidia_video_execution_proved':False,'system_modified':False}
    a.out.write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':record['status'],'frames':record['frames'],'bytes':record['bytes_compared']}))
if __name__=='__main__':main()
