"""Raw conversion fixtures and an integer-only IEEE binary64 reference.

The GPU compiler uses NIR conversion operations. This oracle instead builds
the sign, exponent and significand with integer arithmetic and tie-to-even.
No expected result is part of the uploaded fixtures.
"""
import struct

MASK = (1 << 64) - 1
OPS = ('from_i64', 'from_u64', 'from_f32')
INTEGER_EDGES = [
    0, 1, 2, (1 << 32) - 1, 1 << 32, (1 << 32) + 1,
    (1 << 52) - 1, 1 << 52, (1 << 53) - 1, 1 << 53,
    (1 << 53) + 1, (1 << 53) + 3, (1 << 54) - 1,
    (1 << 54) + 2, (1 << 54) + 6, (1 << 60) - 128,
    (1 << 60) + 128, (1 << 60) + 384,
    (1 << 63) - 1, 1 << 63, (1 << 63) + 1, MASK,
]
INTEGER_EDGES += [(-v) & MASK for v in INTEGER_EDGES[1:]]
FLOAT_EDGES = [
    0, 0x80000000, 1, 0x80000001, 0x007fffff, 0x807fffff,
    0x00800000, 0x80800000, 0x7f7fffff, 0xff7fffff,
    0x7f800000, 0xff800000, 0x7fc00042, 0xffc00042,
    0x7f800001, 0xff800001, 0x3f800000, 0xbf800000,
    0x3f800001, 0x3f7fffff, 0x40000000, 0xc0000000,
    0x3f000000, 0xbf000000, 0x00800001, 0x00000002,
]


def columns(op, local, count, trial):
    assert op in OPS and local in (32, 128, 1024) and trial in (0, 1, 2)
    state = 0x880c20261014 + 97 * local + 104729 * trial
    result = [[], [], []]
    edges = FLOAT_EDGES if op == 'from_f32' else INTEGER_EDGES
    for i in range(count):
        for col in range(3):
            state = (state * 6364136223846793005 + 1442695040888963407) & MASK
            raw = state
            if col == 0 and i < len(edges):
                raw = edges[(i + trial * 11) % len(edges)]
            if col == 0 and op == 'from_f32':
                # Deliberately nonzero/different upper words test that only
                # the binary32 low word is read by the conversion.
                raw = (state & 0xffffffff00000000) | (raw & 0xffffffff)
            result[col].append(raw)
    return result


def integer_to_binary64(n):
    if n == 0:
        return 0
    sign = int(n < 0) << 63
    n = abs(n)
    exponent = n.bit_length() - 1
    shift = n.bit_length() - 53
    if shift <= 0:
        significand = n << -shift
    else:
        significand = n >> shift
        remainder = n & ((1 << shift) - 1)
        halfway = 1 << (shift - 1)
        if remainder > halfway or (remainder == halfway and significand & 1):
            significand += 1
        if significand == 1 << 53:
            significand >>= 1
            exponent += 1
    return sign | ((exponent + 1023) << 52) | (significand & ((1 << 52) - 1))


def expected_bits(op, raw):
    if op == 'from_i64':
        return integer_to_binary64(raw - (1 << 64) if raw >> 63 else raw)
    if op == 'from_u64':
        return integer_to_binary64(raw)
    assert op == 'from_f32'
    raw &= 0xffffffff
    sign = (raw >> 31) << 63
    exponent = (raw >> 23) & 255
    fraction = raw & 0x7fffff
    if exponent == 255:
        return sign | (0x7ff << 52) | ((fraction << 29) | (1 << 51) if fraction else 0)
    if exponent:
        return sign | ((exponent - 127 + 1023) << 52) | (fraction << 29)
    if fraction == 0:
        return sign
    width = fraction.bit_length()
    return sign | ((width - 1 - 149 + 1023) << 52) | ((fraction << (53 - width)) & ((1 << 52) - 1))


def equivalent(observed, expected):
    if (expected >> 52) & 0x7ff == 0x7ff and expected & ((1 << 52) - 1):
        return (observed >> 52) & 0x7ff == 0x7ff and bool(observed & (1 << 51))
    return observed == expected


def packed(values):
    return struct.pack('<' + 'Q' * len(values), *values)
