"""CPU-only graph tests; synthetic instructions are never sent to a GPU."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from trace_native_cas_flow import trace_region


def graph(*ops):
    return [(8*(i+1),op) for i,op in enumerate(ops)]


class CASMustAliasFlow(unittest.TestCase):
    def trace(self,ops,old=6,expected=0):
        return trace_region(graph(*ops),0,len(ops)-1,old,expected)

    def test_copy_survives_overwrite_on_both_paths(self):
        result=self.trace(['mov b32 $r5 $r6','$p1 bra 0x20','mov b32 $r6 0x0',
                           'nop','set $p0 0x1 eq u32 $r0 $r5'])
        self.assertEqual(result['aliases_at_comparison'],[5])

    def test_conditional_branch_can_skip_the_copy(self):
        result=self.trace(['$p1 bra 0x18','mov b32 $r5 $r6','mov b32 $r6 0x0',
                           'set $p0 0x1 eq u32 $r0 $r5'])
        self.assertNotIn(5,result['aliases_at_comparison'])

    def test_predicated_copy_is_not_a_must_alias(self):
        result=self.trace(['$p1 mov b32 $r5 $r6','mov b32 $r6 0x0',
                           'set $p0 0x1 eq u32 $r0 $r5'])
        self.assertEqual(result['aliases_at_comparison'],[])

    def test_loop_backedge_converges_to_the_safe_intersection(self):
        result=self.trace(['mov b32 $r5 $r6','mov b32 $r6 0x0','$p1 bra 0x8',
                           'set $p0 0x1 eq u32 $r0 $r5'])
        self.assertNotIn(5,result['aliases_at_comparison'])

    def test_alias_vector_clobber_is_not_ignored(self):
        result=self.trace(['mov b32 $r5 $r6','mov b128 $r4q $r12q',
                           'set $p0 0x1 eq u32 $r0 $r5'])
        self.assertNotIn(5,result['aliases_at_comparison'])

    def test_comparison_input_clobber_refused(self):
        for op in ('mov b32 $r0 0x0','$p1 mov b32 $r0 $r8','join mov b32 $r0 $r8'):
            with self.subTest(op=op),self.assertRaises(ValueError):
                self.trace(['mov b32 $r5 $r6',op,'set $p0 0x1 eq u32 $r0 $r5'])

    def test_unknown_control_or_instruction_refused(self):
        for op in ('join nop','joinat 0x18','call 0x18','prmt b32 $r5 $r6 $r7'):
            with self.subTest(op=op),self.assertRaises(ValueError):
                self.trace([op,'set $p0 0x1 eq u32 $r0 $r6'])

    def test_branch_leaving_slice_refused(self):
        with self.assertRaises(ValueError):
            self.trace(['$p1 bra 0x80','set $p0 0x1 eq u32 $r0 $r6'])

    def test_external_branch_into_slice_refused(self):
        ops=graph('bra 0x18','mov b32 $r5 $r6','nop','set $p0 0x1 eq u32 $r0 $r5')
        with self.assertRaises(ValueError):trace_region(ops,1,3,6,0)

    def test_nonlocal_call_outside_slice_refused(self):
        ops=graph('call 0x18','mov b32 $r5 $r6','nop','set $p0 0x1 eq u32 $r0 $r5')
        with self.assertRaises(ValueError):trace_region(ops,1,3,6,0)

    def test_reconvergence_target_inside_slice_refused(self):
        ops=graph('joinat 0x18','mov b32 $r5 $r6','nop','set $p0 0x1 eq u32 $r0 $r5')
        with self.assertRaises(ValueError):trace_region(ops,1,3,6,0)

    def test_join_at_entry_is_an_explicit_assumption(self):
        ops=graph('joinat 0x10','mov b32 $r5 $r6','set $p0 0x1 eq u32 $r0 $r5')
        self.assertIn(5,trace_region(ops,1,2,6,0)['aliases_at_comparison'])


if __name__=='__main__':unittest.main()
