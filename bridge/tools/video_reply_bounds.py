#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Conservative offline length check for a prospective video-buffer reply.

This is not attached to a driver, and does not validate resource contents,
ownership, kernel acceptance or a private ABI. The caller must first qualify
its exact profile and obtain a legitimate response through an authorized path.
"""
HEADER_BYTES = 48
MAX_REPLY_BYTES = 4096


def checked_reply(status, capacity, returned, private_bytes, payload):
    """Return bounded header and private slices or raise ValueError.

    Requiring the entire requested reply is deliberately stricter than the
    observed user-mode comparison. No driver call is made and no data is
    fabricated when the supplied reply is incomplete.
    """
    if any(type(v) is not int for v in (status, capacity, returned, private_bytes)):
        raise ValueError('integer fields required')
    if status != 0:
        raise ValueError('request did not succeed')
    if private_bytes < 0 or private_bytes > MAX_REPLY_BYTES - HEADER_BYTES:
        raise ValueError('private length out of bounds')
    expected = HEADER_BYTES + private_bytes
    if capacity != expected or returned != expected:
        raise ValueError('incomplete or inconsistent reply length')
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise ValueError('byte buffer required')
    try:
        view = memoryview(payload).cast('B')
    except (TypeError, ValueError) as exc:
        raise ValueError('contiguous byte buffer required') from exc
    if len(view) < returned:
        raise ValueError('payload shorter than reported length')
    return bytes(view[:HEADER_BYTES]), bytes(view[HEADER_BYTES:returned])
