"""Synthetic encoded-word tests only; these fixtures are never submitted toGPU."""
import hashlib
import struct
import unittest

from propose_native_control_reserve import propose, Refused, path_abstraction

SCHEDULE = 0x2000000000000007
NOP = 0x4000000000001de4
JOIN = NOP | 16


def control(opcode, pc, target=None, pred=7):
    word = (opcode << 58) | (pred << 10) | 7
    if opcode in [0x10, 0x20]:
        word |= 15 << 5
    if target is not None:
        word |= ((target - pc - 8) & 0xffffff) << 26
    return word


def sample(overrides=None, size=16):
    entries = [(SCHEDULE, 'sched 0x0') if i % 8 == 0 else (NOP, 'nop') for i in range(size)]
    entries[1] = control(0x18, 8, 32), 'joinat 0x20'
    entries[3] = JOIN, 'join nop'
    entries[4] = control(0x20, 32), 'exit'
    for i, pair in (overrides or {}).items():
        entries[i] = pair
    raw = b''.join(struct.pack('<Q', w) for w, _ in entries)
    listing = '\n'.join(f'{8*i:08x}: {w&0xffffffff:08x} {w>>32:08x}     {text}'
                        for i, (w, text) in enumerate(entries))
    metadata = [0] * 58
    metadata[0], metadata[7] = size - 1, 1
    return raw, listing, metadata, hashlib.sha256(raw).hexdigest()


class ControlProposalTests(unittest.TestCase):
    def refusal(self, gate, args):
        with self.assertRaises(Refused) as cm:
            propose(*args)
        self.assertEqual(cm.exception.gate, gate)

    def test_valid_model_never_grants_hardware_authorization(self):
        p = propose(*sample())
        self.assertEqual(p['maximum_abstract_path_depth'], 1)
        self.assertEqual(p['status'], 'KEEP_NATIVE_PROPOSAL')
        self.assertFalse(p['hardware_upper_bound_certified'])
        self.assertFalse(p['automatic_runtime_application'])

    def test_native_schedule_target_is_accepted(self):
        overrides = {1: (NOP, 'nop'), 2: (control(0x10, 16, 64), 'bra 0x40'),
                     3: (NOP, 'nop'), 9: (control(0x20, 72), 'exit')}
        self.assertEqual(propose(*sample(overrides))['maximum_abstract_path_depth'], 0)

    def test_unreachable_tail_branch_on_cache_boundary_is_accepted(self):
        self.assertEqual(propose(*sample({8: (control(0x10, 64, 64), 'B bra 0x40')}))
                         ['maximum_abstract_path_depth'], 1)

    def test_code_hash_mismatch_is_refused(self):
        raw, text, words, h = sample()
        self.refusal('code_hash', (raw[:-1] + bytes([raw[-1] ^ 1]), text, words, h))

    def test_listing_words_are_independently_checked(self):
        raw, text, words, h = sample()
        text = text.replace('00000010: 00001de4', '00000010: 00001de5')
        self.refusal('listing_word', (raw, text, words, h))

    def test_unknown_exec_opcode_is_refused(self):
        self.refusal('unsupported_exec_opcode', sample({2: (control(0x24, 16), 'ret')}))

    def test_unhandled_branch_modifier_is_refused(self):
        self.refusal('exec_reserved_bits', sample({2: (control(0x10, 16, 32) | (1 << 15), 'bra 0x20')}))

    def test_backward_joinat_is_refused(self):
        self.refusal('joinat_forward', sample({1: (control(0x18, 8, 8), 'joinat 0x8')}))

    def test_predicated_joinat_is_refused(self):
        self.refusal('predicated_joinat', sample({1: (control(0x18, 8, 32, 0), '$p0 joinat 0x20')}))

    def test_crossing_regions_are_refused(self):
        self.refusal('crossing_regions', sample({1: (control(0x18, 8, 96), 'joinat 0x60'),
                                                 2: (control(0x18, 16, 104), 'joinat 0x68')}))

    def test_empty_abstract_stack_is_refused(self):
        self.refusal('abstract_underflow', sample({1: (NOP, 'nop')}))

    def test_push_cycle_hits_explicit_depth_limit(self):
        self.refusal('abstract_depth_cap', sample({1: (control(0x18, 8, 56), 'joinat 0x38'),
                                                   2: (control(0x10, 16, 8), 'bra 0x8')}))

    def test_state_budget_is_a_refusal_not_a_certificate(self):
        with self.assertRaises(Refused) as cm:
            path_abstraction({0: ('STEP', None, 7), 8: ('EXIT', None, 7)}, max_states=1)
        self.assertEqual(cm.exception.gate, 'abstract_state_cap')

    def test_target_outside_program_is_refused(self):
        self.refusal('target_not_instruction', sample({2: (control(0x10, 16, 128), 'bra 0x80')}))

    def test_target_must_match_the_encoded_displacement(self):
        self.refusal('branch_target', sample({2: (control(0x10, 16, 72), 'bra 0x40')}))

    def test_boolean_metadata_is_refused(self):
        raw, text, words, h = sample()
        words[7] = True
        self.refusal('metadata_integer_words', (raw, text, words, h))

    def test_unknown_annotations_are_refused(self):
        raw, text, words, h = sample()
        self.refusal('unknown_decode', (raw, text + '\n[unknown]', words, h))

    def test_missing_listing_word_is_refused(self):
        raw, text, words, h = sample()
        self.refusal('incomplete_listing', (raw, text.rsplit('\n', 1)[0], words, h))


if __name__ == '__main__':
    unittest.main()
