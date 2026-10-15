#!/usr/bin/env python3
"""Adapt historical oracles to the SDK launcher's attested signed basename."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--variant',choices=['manifest','grid3d'],required=True);p.add_argument('--portable',action='store_true');a=p.parse_args()
root=a.input.resolve();m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
assert m['GPU_reservation']['state']=='terminal'
if not a.portable:
    assert sha(root/('cpu_icb_'+a.variant+'_probe'))==inp['executable_SHA256']==m['original_binary_sha256']
    assert Path(m['signed_executable']).name=='application'
    assert sha(root/'execution/application')==m['signed_binary_sha256']
source=Path(__file__).with_name('verify_cpu_icb_'+a.variant+'.py')
spec=importlib.util.spec_from_file_location('legacy_oracle',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
# The numerical/packet oracle stays unchanged. Actual host identities above
# replace its assumption about the historical run_signed_probe basename.
v=module.verify(root,portable=True)
v.update(portable_raw_verification_only=a.portable,host_executable_SHA256_rechecked=not a.portable,
         signed_basename_adapter='manifest-attested SDK execution/application',
         adapter_SHA256=sha(Path(__file__)))
target=root/'sdk-independent-verification.json';assert not target.exists();target.write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps({k:x for k,x in v.items()if k not in ['raw_SHA256','packet_records']},indent=2))
