# Loaded video providers and the AppleVA eligibility gate

A bounded, process-local experiment identifies a model-policy gate in the
installed AppleVA availability query. It does **not** demonstrate hardware video
decoding, explain the global H.264 failure, or modify the installed stack.

## Actual loaded components

The observer uses public dyld add/remove callbacks and copies Mach-O load
commands while the image is mapped. An original CPU fixture returning 37
calibrates load and removal: 349 → 350 → 349 active images. Two catalogue
versions are retained; the later version preserves every `LC_BUILD_VERSION`
command instead of interpreting its last entry as the running platform.

| Component | Loaded version | Loaded UUID |
| --- | --- | --- |
| AppleVA | 5.1.1 | `7533f7872ca53a968dc5fa34f9035e37` |
| VideoToolbox | 3330.13.105 | `e7231bea63883d0a95c0a93ce970b96b` |

AppleGVA is absent from the recorded images and no-load lookups in these
processes. This does not describe other processes. VideoToolbox depends on
AppleVA; its six direct AVAFQT imports do not establish which provider its H.264
path uses. Link-time dependency versions are not loaded runtime versions, and an
image UUID is not a file hash. The current VideoToolbox image is cache-resident;
its install path is not a separately readable executable on this system.

Offline bounded reads of the installed shared cache match those UUIDs. The main
cache file SHA-256 is
`01d2fb67994fe5f4a6846263144432af24a1a450993f917e54de53351e6708be`.
Code regions, disassembly and analysis objects remain private. The original
generic cache inspector and analysis-object wrapper are published as source;
the wrapper creates an ELF relocatable text section for analysis, never an
executable vendor image. No entire shared-cache extraction was performed.

## Causal availability experiment

Static inspection establishes the exact contract of this pinned
`VP3IsAvailable`: **`int32_t(void)`**, status 0 or -8973, not a Boolean.
Its first helper reads `AppleVADriver.bundle/Contents/Info.plist`, requires a
`System Support` entry for `hw.model`, and the current table lacks `iMac11,1`.
The next helper recognizes the NVIDIA video renderer properties already present
on the reference machine. Decoder factory/decode ABIs remain unestablished and
were not called.

The host first checks the resident UUID, query address, and exact SHA-256 of the
136-byte query and its 580/1,535-byte helpers. An inspect-only process validates
these without calling the query. The optional observer replaces only returned
policy **data** at pinned native caller offset 267,793 and an explicitly marked
synthetic calibration call, on its configuring thread. It leaves the original
system file and all instructions intact.

| Fresh-process query condition | Processes | Actual status |
| --- | --- | --- |
| Original system table, including a final restoration control | 4 | -8973 |
| Original minimal test table with a different model key | 3 | -8973 |
| Same minimal table with `iMac11,1` | 3 | 0 |

The minimal tables each contain one model entry and explicit false values for
`boostIG` and `disallowBGRA`. Each query records the exact native CFURL caller,
verified original policy hash and whether returned data was replaced. The
synthetic call is counted separately. This supports a causal eligibility result
for **this query and binary**, not a working decoder or system-wide fix.

## Qualification and limits

The [recalculated summary](video-eligibility-validation.json) covers 17 terminal,
nonoverlapping native processes: six catalogue/API controls and eleven policy
processes. These are separate from the thirteen earlier transport processes.
The ABI self-test adds 256 synthetic cases. The software control again matches
six existing independent CPU reference frames / 691,200 active NV12 bytes
exactly; no new M1 execution was needed. The hardware-required VT create still
returns -12906 and legacy VDA -12473 before images.

The 83 existing system-file pins, an additional AppleVA policy file, OCLP and 36
common runtime sources remain unchanged. No Metal feature, video-engine
execution, installed-driver modernization or speedup is claimed. Performance
benchmark and system deployment are **NOT RUN**.

The next informative step is a valid public-API decoding experiment that can
establish whether this gate is reached in a real codec path, with an independent
CPU image oracle. Availability success alone is insufficient.

## Reproduction

On the **exact inspected target profile**, from `bridge`, use fresh directories
and the existing shared laboratory reservation root:

```sh
python3 tools/native_video_policy.py build --out results/video-policy-new-build
python3 tools/native_video_policy.py run --build results/video-policy-new-build \
  --out results/video-policy-new-inspect --mode inspect
```

Validate inspect-only pins before running `native`, then `wrong-model`, then
`model-entry` in separate new result directories. Changed resident code/profile
is a refusal, not permission to update hashes automatically. The host invokes no
decoder factory and changes no system setting. The original observer is linked
into the test application; there is no external-process injection.

`build_video_images.py` / `run_video_images.py` build and run the image observer
with the locally regenerated thirteen-file fixture described in
[the transport guide](VIDEO_TRANSPORT.md). `audit_video_images.py --lab-root
/absolute/path/to/original/bridge --out /new/audit.json` recalculates named
historical private receipts. A clean checkout omits those receipts, pixels and
vendor regions and cannot claim their execution from the summary.

Reference formats: Apple's
[dyld callbacks](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man3/dyld.3.html)
and [cache structures at the inspected revision](https://github.com/apple-oss-distributions/dyld/blob/fd8d0c4d52320ebf64db34f3cb280310d905c5ae/include/mach-o/dyld_cache_format.h).
These explain observation/parser formats, not private AppleVA compatibility.
