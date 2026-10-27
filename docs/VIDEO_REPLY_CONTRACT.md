# Video-buffer reply: static bounds and private tail

A new offline analysis connects the earlier **49-byte user-mode capacity** to
the installed kernel and NVIDIA code. It does not call a device or demonstrate
a successful video-buffer allocation.

For the pinned on-disk files, the inherited `get_data_buffer` function checks
for at least an eight-byte input and a 48-byte output capacity. Its instructions
pass a null private pointer when capacity equals 48; for a larger capacity they
pass `output + 48` and `capacity - 48` to virtual slot `0xa68`. The NVIDIA
video-context vtable resolves that slot in the file to the inherited
`getDataBuffer` method. That method eventually calls virtual slot `0xa78` with
the private pointer and length. The NVIDIA vtable entry for `0xa78` points to
a six-byte function at `0x683b0` which returns without writing. REA/Ghidra
independently recorded the complete body as evidence
`ev_e5a940d04aea0c79af48881f137812f2fcd7dbb6e0bed3d7fb59e1d53b74ad96`.
The other kernel observations use evidence
`ev_9ef4aee42a6f2eee153d0e5ff80c39bb8a4771f391d11562decd68341dbbbd03`
and `ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9`.

This is a static file interpretation: live relocated vtables and execution were
not observed. A no-write function alone does **not** establish whether another
layer initializes or uses the private byte. The prior 49-byte capacity was
observed at a guard which refused the request; it was not a returned response.

On the pinned user-mode success branch, the wrapper checks that the returned
length is not **greater** than the original capacity, then passes the original
private length to the resource constructor. That constructor copies that many
bytes starting 48 bytes into the output allocation. The inspected success
branch does not visibly require the returned length to cover that copy. A
hypothetical short *successful* response therefore needs separate handling;
no such real response, vulnerability, or exploit has been demonstrated. The
copy described here is within the originally allocated response capacity, but
some bytes could be outside a hypothetical shorter reported result. This does
not establish their initialization or any downstream effect.

## Conservative offline check

[`video_reply_bounds.py`](../bridge/tools/video_reply_bounds.py) provides an
independent CPU-only preflight for prospective integration. It accepts success
only when the reported and supplied response cover the full 48-byte header and
all expected private bytes, with a 4 KiB local safety cap. It returns separate
header and private byte slices; it does not interpret resource IDs, certify
ownership, call a driver, or patch the installed wrapper. The 4 KiB cap is a
project policy, not a discovered driver limit. For the observed 49-byte
capacity and one private byte, synthetic reported lengths 0, 47, 48 and 50 are
refused and 49 is accepted. Four unit tests exercise exact, truncated, error,
type and capacity cases.

The [validation record](video-reply-contract-validation.json) contains the
pinned identifiers and hash-bound observations. A separately altered REA record
was rejected by the auditor. This is not a driver fix, Metal API extension or
runtime test; valid resource contents, live kernel dispatch, mapping, object
ownership, and cleanup remain unqualified.

## Reproduction

The REA captures and disassemblies contain proprietary code and remain in the
local lab. The auditor checks their hashes against the installed files and
requires the exact prior captures, cache UUID and fresh output path:

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
python3 bridge/tools/video_reply_contract.py \
  --geforce /System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce \
  --cache /System/Volumes/Preboot/Cryptexes/OS/System/Library/dyld/dyld_shared_cache_x86_64 \
  --getdata "$LAB/results/video-method-contract-20261027/get-data-buffer.private.json" \
  --getbuffer "$LAB/results/video-method-contract-20261027/getDataBuffer.private.json" \
  --tail-rea "$LAB/results/video-nvidia-private-tail-20261027-01/0x683b0.private.json" \
  --user-audit "$LAB/results/video-buffer-user-audit-20261027-02" \
  --out "$LAB/results/video-reply-contract-new.json"
python3 -m unittest discover -s tests -p test_video_reply_bounds.py -v
```

The exact retained disassemblies include their original paths; a new analysis
must be separately qualified rather than silently accepted under these pins.
No system component, driver, OCLP configuration or firmware was modified.
