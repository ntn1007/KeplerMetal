# Video data-buffer size: conditional static path and CPU helper

The installed, hash-pinned `IOAcceleratorFamily2` implementation contains a
qualification relevant to any future video client: **a requested buffer size
is not, by itself, proof of the returned buffer's size**.

The original `getDataBuffer` entry at `0x9f70` obtains the class and checks its
context-dependent limit. In its initial conditional region, a null pointer at
the selected class's `+0x28` jumps from `0x9fd2` to `0xa031`, past the load of
the second input word at `0x9fe5` and the call to the size-update helper at
`0x9fff`. If the pointer is non-null and the inspected current size is below
the stored bound, the other branch considers that second word and calls the
helper. This is an **on-disk control-flow observation**, not a trace of a live
video request. It does not establish what later code or an allocator returns.

The inherited `getDataBufferLimits` and `contextStart` instructions describe
two class records on a conditional initialization path. For both records the
observed initial size field is 65,536 bytes, the upper size field is 524,288
bytes and the growth field is 2. The NVIDIA video-context file has a relocation
to that inherited method. The actual live vtable target, class state and
conditional initialization have not been observed. These numbers are **not**
proof of current GPU allocation or a guarantee for a different profile.

## Helper verification

The original 145-byte CPU helper at `0x9ede` adds 8,192 to its input, grows the
modeled value using the stored multiplier, bounds it by the upper field and
rounds according to the supplied page-size value. Under the tested initial
fields, a direct helper input of 131,072 and a synthetic 4 KiB page size
produces a 262,144-byte size field. This is a controlled helper result, **not**
the outcome of a kernel request for 128 KiB. Another output field is also
updated; the test compares all bytes of the synthetic context, not only the
first field.

The [offline auditor](../bridge/experiments/video_buffer_size_offline/audit.py)
verifies the original images, method-table and vtable links, source-bound REA
evidence, selected raw-code hashes and relative branch targets. It then runs
only that pinned helper in a separate CPU process, on synthetic context memory;
the sole external page-size pointer is supplied by the test. It compares
**4,096 cases** against an independently written calculation, including two
synthetic page sizes and boundary values. The test uses writable-then-executable
private memory and checks the helper's SHA-256 before executing it. A changed
helper is refused before execution. No GPU connection is opened.
[Validation record](video-buffer-size-path-validation.json).

This changes the next integration requirement: even after a legitimate request
and its ownership contract are qualified, a client must verify the **actual
returned mapping and usable length** before copying staged video data. The
present result does not qualify a selector, a returned resource, a mapping, a
video channel, decoding or performance. The earlier local guard still refuses
the unqualified request. No macOS, driver or OCLP component was modified.

## Reproduction

The original proprietary images and REA evidence remain outside this
repository. The exact captured evidence bundle is needed for this particular
audit; a newly captured bundle requires independent requalification, not
silent repinning. Use a fresh output directory in the private lab:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/experiments/video_buffer_size_offline/audit.py \
  --ioaccel /System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2 \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --prior-rea "$LAB/results/video-command-contract-progress-20261018/IOAccel-command-contract-final.private.json" \
  --get-buffer-rea "$LAB/results/video-method-contract-20261027/getDataBuffer.private.json" \
  --new-rea "$LAB/results/video-desired-size-20261029-01.private.json" \
  --out "$LAB/results/new-buffer-size-audit"
```

The output directory contains a local copy of the original code bytes and must
not be published. REA 6.4.0/Ghidra 12.1.4 recorded the size helper as evidence
`ev_d2cf4c019488b13eab432078e37e85d8b9fa3c547f9958c38a62f2556aede5dc`;
the earlier `getDataBuffer` and limit records are identified in
[VIDEO_METHOD_CONTRACT.md](VIDEO_METHOD_CONTRACT.md).
