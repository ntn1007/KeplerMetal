# SPDX-License-Identifier: MIT
import struct
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_typed_render_draw import transform,why,SEEDS
from verify_render_state_catalogue import source_record


class TypedDrawRasterContract(unittest.TestCase):
    def record(self,mode,trial):return struct.unpack('<8IQ6I',transform(mode,trial,0,source_record(trial,0,'gpu',[1,2],[3,4])))

    def test_draw_replaces_geometry_but_preserves_identity(self):
        for trial in range(8):
            before=struct.unpack('<8IQ6I',source_record(trial,0,'gpu',[1,2],[3,4]));after=self.record('draw_gpu',trial)
            self.assertEqual(after[8],before[8]);self.assertEqual(after[1],0);self.assertEqual(after[4],5+3*((SEEDS[trial]>>3)&1))

    def test_six_vertices_cover_both_triangles(self):
        r=self.record('draw_gpu',2);self.assertEqual(r[2:5],(6,1,5))

    def test_draw_repairs_preceding_wrong_kind(self):
        self.assertEqual(struct.unpack('<8IQ6I',source_record(3,0,'gpu',[1,2],[3,4]))[1],1)
        r=self.record('draw_gpu',3);self.assertEqual(why('draw_gpu',3,0,[1,2].index(r[8]),2,[r],[1,2],'gpu'),0)

    def test_outside_sealed_draw_envelope_refused(self):
        for trial in [4,5]:
            r=self.record('draw_gpu',trial);self.assertEqual(why('draw_gpu',trial,0,[1,2].index(r[8]),0,[r],[1,2],'gpu'),3)

    def test_reset_order_changes_liveness(self):
        r=self.record('draw_then_reset',0);self.assertEqual(r,(0,)*15)
        self.assertEqual(why('draw_then_reset',0,0,0,0,[r],[1,2],'gpu'),1)
        r=self.record('draw_after_reset',0);self.assertEqual(r[0],0x4b505353);self.assertEqual(r[8],0)
        self.assertEqual(why('draw_after_reset',0,0,0,0,[r],[1,2],'gpu'),5)

    def test_missing_dispatch_preserves_defect_and_empty_trial(self):
        for trial in [3,7]:
            original=source_record(trial,0,'gpu',[1,2],[3,4]);self.assertEqual(transform('draw_no_dispatch',trial,0,original),original)

    def test_other_draw_slots_never_changed(self):
        for trial in range(8):
            for slot in [1,2,3]:
                original=source_record(trial,slot,'gpu',[1,2],[3,4]);self.assertEqual(transform('draw_gpu',trial,slot,original),original)


if __name__=='__main__':unittest.main()
