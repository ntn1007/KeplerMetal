#!/usr/bin/env python3
"""CPU-only executable model of the bounded SM30 division experiment.

The reciprocal is rounded normally, then perturbed by -1/0/+1 ULP. This checks
the arithmetic construction, not the actual NAK reciprocal or GPU execution.
Both the old round-to-odd failure and the new residual-aware rule are retained.
"""
from pathlib import Path
import argparse, ctypes, hashlib, json, math, struct
from fractions import Fraction

MASK = (1 << 52) - 1
SIGN = 1 << 63
INF = 0x7ff0000000000000
QNAN = 0x7ff8000000000000
libc = ctypes.CDLL(None)
fma = libc.fma
fma.argtypes = [ctypes.c_double] * 3
fma.restype = ctypes.c_double

def bits(x):
    return struct.unpack('<Q', struct.pack('<d', x))[0]

def value(x):
    return struct.unpack('<d', struct.pack('<Q', x))[0]

def normalize(x):
    x = abs(x)
    sub = x != 0 and ((bits(x) >> 52) & 2047) == 0
    y = x * 2.0**54 if sub else x
    e = ((bits(y) >> 52) & 2047) - 1023 - (54 if sub else 0)
    return value((bits(y) & MASK) | (1023 << 52)), e

def model(a, b, perturb, old):
    s = (bits(a) ^ bits(b)) & SIGN
    if math.isnan(a) or math.isnan(b) or (a == 0 and b == 0) or (math.isinf(a) and math.isinf(b)):
        return QNAN
    if math.isinf(a) or b == 0:
        return s | INF
    if a == 0 or math.isinf(b):
        return s
    ma, ea = normalize(a)
    mb, eb = normalize(b)
    reciprocal = value(bits(1.0 / mb) + perturb)
    q = ma * reciprocal
    for _ in range(2):
        q = fma(fma(-q, mb, ma), reciprocal, q)
    residual = fma(-q, mb, ma)
    qe = ((bits(q) >> 52) & 2047) + ea - eb
    if qe >= 2047:
        return s | INF
    if qe > 0:
        return s | (bits(q) & MASK) | (qe << 52)
    if old and not (bits(q) & 1) and residual != 0:
        q = value(bits(q) + (1 if residual > 0 else -1))
        qe = ((bits(q) >> 52) & 2047) + ea - eb
    shift = 1 - qe
    if shift > 53:
        return s
    significand = (bits(q) & MASK) | (1 << 52)
    quotient, remainder = divmod(significand, 1 << shift)
    middle = 1 << (shift - 1)
    tie_up = bool(quotient & 1) if old else residual > 0 or (residual == 0 and bool(quotient & 1))
    return s | (quotient + int(remainder > middle or (remainder == middle and tie_up)))

def reference(a, b):
    if math.isnan(a) or math.isnan(b) or (a == 0 and b == 0) or (math.isinf(a) and math.isinf(b)):
        return QNAN
    s = (bits(a) ^ bits(b)) & SIGN
    if math.isinf(a) or b == 0:
        return s | INF
    if a == 0 or math.isinf(b):
        return s
    try:
        return bits(float(Fraction.from_float(a) / Fraction.from_float(b)))
    except OverflowError:
        return s | INF

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--inputs', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    assert not a.out.exists()
    pairs, source_hashes = [], {}
    for trial in range(3):
        cols = []
        for col in ['A', 'B']:
            path = a.inputs / f'l1024-t{trial}-{col}.bin'
            raw = path.read_bytes()
            source_hashes[path.name] = hashlib.sha256(raw).hexdigest()
            cols.append(struct.unpack('<' + 'd' * (len(raw) // 8), raw))
        pairs.extend(zip(*cols))
    # Observed old-rule failure and exact ties / near ties over all subnormal
    # output precisions. These are extra CPU cases, not GPU qualification.
    pairs.append((value(0xb8ec2d208cf9e3bc), value(0x78d1054113bacd5b)))
    for shift in range(1, 55):
        for low in [0, 1, (1 << 51), (1 << 52) - 1]:
            for delta in [-1, 0, 1]:
                num = value((1 << 52) | low)
                den = value(((1023 + shift) << 52) + delta)
                pairs.append((num, den))
                pairs.append((-num, den))
    failures = {'round_to_odd': [], 'residual_midpoint': []}
    counts = dict.fromkeys(failures, 0)
    checks = 0
    for a0, b0 in pairs:
        ref = reference(a0, b0)
        for perturb in [-1, 0, 1]:
            checks += 1
            for key, old in [('round_to_odd', True), ('residual_midpoint', False)]:
                ob = model(a0, b0, perturb, old)
                ok = math.isnan(value(ob)) if math.isnan(value(ref)) else ob == ref
                if not ok:
                    counts[key] += 1
                    if len(failures[key]) < 32:
                        failures[key].append({'a': f'{bits(a0):016x}', 'b': f'{bits(b0):016x}', 'observed': f'{ob:016x}', 'expected': f'{ref:016x}', 'reciprocal_perturb_ULP': perturb})
    d = {'status': 'PASS' if not counts['residual_midpoint'] else 'FAIL', 'checks_per_rule': checks, 'pair_count': len(pairs), 'failures_count': counts, 'failures': failures, 'input_SHA256': source_hashes, 'script_SHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'CPU_reference': 'exact Fraction division rounded once to binary64', 'GPU_execution': False, 'exhaustive_proof': False}
    a.out.write_text(json.dumps(d, indent=2) + '\n')
    print(json.dumps({k: v for k, v in d.items() if k not in ['failures', 'input_SHA256']}, indent=2))
    return 0 if d['status'] == 'PASS' else 1

if __name__ == '__main__':
    raise SystemExit(main())
