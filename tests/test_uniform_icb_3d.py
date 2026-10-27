# SPDX-License-Identifier: MIT
import sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
import audit_uniform_icb_3d as audit
class AuditTests(unittest.TestCase):
    def test_pairs_compare_data_but_not_relocated_command_buffers(self):
        expected=[('prepare','groups'),('prepare','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads'),('execute','groups'),('execute','threads')];rows={};paths=[]
        for j,(mode,form) in enumerate(expected):
            p=Path('/fake')/str(j);paths.append(p);count=36 if mode=='prepare' else 180
            raw={f'data-{n}.bin':'same' for n in range(count)};raw['trial-0.commands.bin']=f'relocated-{j}'
            v={'mode':mode,'form':form,'gpu_registry_id':55,'raw_SHA256':raw,'GPU_user_submissions':0 if mode=='prepare' else 7,'GPU_invocations_counted':0 if mode=='prepare' else 18632,'correct_uint32_words':0 if mode=='prepare' else 149056,'dimension_rejection_controls':8,'raw_files_verified':len(raw)}
            i={'build_inputs_SHA256':'build','runtime_archive_SHA256':'archive','library_SHA256':'library','manifest_SHA256':'manifest'};m={'pid':j+1,'started_at':f'2026-10-27T00:00:{j*2:02d}+00:00','completed_at':f'2026-10-27T00:00:{j*2+1:02d}+00:00'};rows[str(p)]={'v':v,'i':i,'m':m}
        def read(path):
            path=Path(path);root=str(path.parent.parent) if path.name=='manifest.json' else str(path.parent);row=rows[root]
            return {'verification-execution.json':{'exit_code':0},'verification.stdout':row['v'],'inputs.json':row['i'],'manifest.json':row['m']}[path.name]
        with patch.object(audit,'verify',side_effect=lambda p:rows[str(p)]['v']),patch.object(audit,'read',side_effect=read),patch.object(audit,'sha',return_value='hash'),patch.object(audit.subprocess,'run'):
            self.assertEqual(audit.audit(paths)['paired_data_files_identical'],540)
            rows[str(paths[3])]['v']['raw_SHA256']['data-1.bin']='different'
            with self.assertRaisesRegex(ValueError,'captures differ'):audit.audit(paths)
            rows[str(paths[3])]['v']['raw_SHA256']['data-1.bin']='same';rows[str(paths[1])]['m']['started_at']='2026-10-27T00:00:00+00:00'
            with self.assertRaisesRegex(ValueError,'overlapped'):audit.audit(paths)
if __name__=='__main__':unittest.main()
