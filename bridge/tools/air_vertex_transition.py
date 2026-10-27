#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline reference model for scoped vertex-buffer state transitions.

This model does not create Metal resources or certify GPU addresses. A future
host must build rows from live, retained, already-certified catalogue objects,
validate their lifetimes and GPU spans, and declare indirect resources. Never
use this module's caller-supplied integers as a GPU authority.
"""
from dataclasses import dataclass
import struct

LIMIT = 1 << 40
MAX_ROWS = 64
ROW = struct.Struct('<QQQII')


@dataclass(frozen=True)
class Binding:
    resource: int
    address: int
    offset: int
    length: int

    def pointer(self):
        if not (0 < self.resource < 1 << 64 and 0 < self.address < LIMIT and
                0 <= self.offset <= self.length <= LIMIT - self.address and
                self.offset % 16 == 0):
            raise ValueError('Uncertifiable binding')
        pointer = self.address + self.offset
        if not 0 < pointer < LIMIT:
            raise ValueError('Binding pointer outside profile')
        return pointer


@dataclass(frozen=True)
class State:
    identity: int
    slot: int
    pipeline: int
    vertices: tuple  # ordered (binding index, Binding) pairs
    fragments: tuple  # opaque canonical resource identities/bindings
    index_binding: tuple  # index object, offset and format, or empty
    geometry: tuple  # complete certified draw envelope


def _validate(state):
    if not (0 < state.identity < 1 << 64 and 0 <= state.slot < 16 and
            0 < state.pipeline < 1 << 64):
        raise ValueError('Invalid state identity, slot or pipeline')
    indices = [i for i, _ in state.vertices]
    if indices != sorted(set(indices)) or any(not 0 <= i < 16 for i in indices):
        raise ValueError('Vertex bindings must be unique, ordered and bounded')
    for _, binding in state.vertices:
        binding.pointer()


def make_rows(states):
    """Return deterministic <source,destination,pointer,slot,binding> rows.

    State identity is unique per logical slot. The target may change only the
    selected vertex binding; all other resource identities and draw envelope
    must be equal. Ambiguous GPU-address aliases invalidate the entire table.
    Null/unbinding and dynamic stride are deliberately not modelled.
    """
    states = tuple(states)
    if not states or len(states) > 16:
        raise ValueError('State count outside catalogue bound')
    for state in states:
        _validate(state)
    keys = [(s.slot, s.identity) for s in states]
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate slot/identity')
    mapping = {}
    for src in states:
        for dst in states:
            if (src.slot, src.pipeline, src.fragments, src.index_binding, src.geometry) != \
               (dst.slot, dst.pipeline, dst.fragments, dst.index_binding, dst.geometry):
                continue
            before, after = dict(src.vertices), dict(dst.vertices)
            for binding, target in dst.vertices:
                if binding not in before:
                    continue
                if {k:v for k,v in before.items() if k != binding} != \
                   {k:v for k,v in after.items() if k != binding}:
                    continue
                key = (src.identity, target.pointer(), src.slot, binding)
                if key in mapping and mapping[key] != dst.identity:
                    raise ValueError('Ambiguous pointer transition')
                mapping[key] = dst.identity
    rows = tuple(sorted((src, dst, pointer, slot, binding)
                        for (src, pointer, slot, binding), dst in mapping.items()))
    if not rows or len(rows) > MAX_ROWS:
        raise ValueError('Transition row count outside profile')
    return rows


def pack_rows(rows):
    if not 0 < len(rows) <= MAX_ROWS:
        raise ValueError('Transition row count outside profile')
    return b''.join(ROW.pack(*row) for row in rows)


def select(rows, source, pointer, slot, binding, stride=(1 << 64)-1):
    """Model one operation; None means fail closed, not native Metal behavior."""
    if stride != (1 << 64)-1 or not 0 < pointer < LIMIT:
        return None
    matches = [dst for src, dst, ptr, command, index in rows
               if (src, ptr, command, index) == (source, pointer, slot, binding)]
    if len(matches) > 1:
        raise ValueError('Ambiguous rows')
    return matches[0] if matches else None
