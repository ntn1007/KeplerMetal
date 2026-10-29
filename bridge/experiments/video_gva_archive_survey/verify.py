#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-check the full survey against the retained narrow inventory."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
HIGH_SHA = 'b48e6eaaacb86400dfc9e84ed85a8df666baa24af7ca3a632b73607a1d2f4cc6'
PRIOR_SHA = '1a1158268d0ed38adc046aa148941a2b4cf160af46b08ef503beefd77999ab80'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('survey', 'prior', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    need(sha(a.prior) == PRIOR_SHA, 'prior inventory digest differs')
    current = json.loads(a.survey.read_text())
    prior = json.loads(a.prior.read_text())
    need(current['status'] == 'PASS_FULL_REGULAR_MEMBER_LITERAL_SURVEY' and
         current['archive_sha256'] == prior['archive_sha256'] == HIGH_SHA and
         current['archive_bytes'] == prior['archive_bytes'] == 5801167872 and
         current['records'] == prior['records'] == 86095 and current['regular_members'] == 54110 and
         current['auditor_sha256'] == sha(HERE/'survey.py'), 'survey provenance differs')
    matches = current['matches']
    indexed = {row['name']: row for row in matches}
    need(len(indexed) == len(matches) == 15, 'matched member count differs')
    controls = prior['controls']
    need(len(controls) == 7, 'prior controls differ')
    for name, old in controls.items():
        need(name in indexed and indexed[name]['sha256'] == old['sha256'] and
             indexed[name]['plist_parse'] == 'ok' and
             indexed[name]['plist_key_values'] == [{'type':'str','string':old['value']}] * old['matches'],
             'control mismatch')
    need(len(prior['nvidia_members']) == 34 and all(row['name'] not in indexed for row in prior['nvidia_members']),
         'prior NVIDIA inventory mismatch')
    need(current['oversize_plists'] == 0 and all(r['plist_parse'] in ('ok','not_plist') for r in matches),
         'matched plist coverage incomplete')
    nvidia_like = [row['name'] for row in matches if '/GeForce' in row['name'] or '/NVDA' in row['name']]
    need(not nvidia_like, 'unexpected NVIDIA-labelled literal')
    receipt = {'status':'PASS_SURVEY_CROSSCHECK', 'survey_sha256':sha(a.survey), 'prior_sha256':sha(a.prior),
               'archive_sha256':HIGH_SHA, 'regular_members':current['regular_members'], 'matching_members':len(matches),
               'earlier_plist_controls_matched':len(controls), 'earlier_nvidia_members_absent':len(prior['nvidia_members']),
               'nvidia_literal_members_found':len(nvidia_like), 'scanned_nested_compression':False,
               'dynamic_producers_excluded':False, 'hardware_video_execution_proved':False,
               'vendor_execution':False, 'GPU_execution':False, 'system_modified':False,
               'verifier_sha256':sha(Path(__file__))}
    with a.out.open('x') as f:
        json.dump(receipt, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'status':receipt['status'], 'matches':len(matches), 'controls':len(controls)}))


if __name__ == '__main__':
    main()
