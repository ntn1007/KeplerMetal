# Native video routing: a second refusal at the service boundary

Three fresh positive H.264 processes reach `com.apple.coremedia.videodecoder`
after the narrowly pinned, process-local `IOGVACodec` presence substitution.
The observed `uber` exchange returns **0**; the following `Strt` exchange
returns **-12906**. Three native and three wrong-key controls have no such
exchanges in the observation scope. All hardware creates still fail with
**zero images**.

This extends the [dependency investigation](VIDEO_DEPENDENCIES.md) in branch A.
It identifies a service boundary after local selection, not a decoder repair,
a new Metal function or the complete root cause.

## Evidence

| Cohort | Terminal host processes | Result |
| --- | ---: | --- |
| First observer | 4 | Inspect, six exact software images, two hardware failures; out-of-range unsigned status omitted |
| Revised observer and controls | 6 | Inspect, 18 exact software images, MPEG-2 hardware failure, passive H.264 positive |
| Rotated native / wrong-key / present-key | 9 | Three repeats per choice, same signed executable and invariant assets |

The [offline audit](video-routing-validation.json) checks all **19** signed,
nonoverlapping host runs and their original shared reservation receipts. It
verifies **1,824 mock ABI calls**, **210 scalar-summary controls**, **310 native
XPC records**, **34 public IOKit controls**, **170 dependency scope checks**,
**24 actual GPU property queries** and **1,882 CF metadata associations**.
Mock controls use owned dictionaries and local mock functions. They send no
native service requests and do not qualify native asynchronous scheduling.

Four software controls produce **24 images / 2,764,800 active NV12 bytes**, with
zero differences from the existing independent FFmpeg references. These reuse
the six original images per codec. All **13 hardware-required requests** return
-12906 before images. Diagnostic completion does not mean hardware success.

The x86_64 test platform is macOS26.7.1/build25G241 with SDK26.2 and Apple
clang17.0.0 (`clang-1700.6.4.2`). VideoToolbox is `3330.13.105`, UUID
`e7231bea63883d0a95c0a93ce970b96b`.
CoreMedia, libxpc and four optional caller modules have exact identities in the
[caller profile](video-routing-profile.json). Existing libraries also validate
six CoreMedia/five VideoToolbox code regions and GPU registry ID `4294968458`.

| Positive hardware exchange | VT return offset | Recorded opcode | Reply Status |
| --- | ---: | --- | ---: |
| First | 6326974 | 1969382770 / `uber` | 0 |
| Following | 6327491 | 1400140404 / `Strt` | -12906 |

The same exchanges return zero in software controls, followed by ordinary
decode messages and six correct images. `uber` and `Strt` are observed four-byte
protocol labels, not documented public operation contracts. Their exact private
implementations are unproved. The error also reaches VT return offsets 6290187
and 20163. The recorded service reply is a dictionary, not an invalid-connection
error.

Observer v1 deliberately omitted unsigned values outside uint32. Some negative
statuses are sign-extended uint64; v2 records only exact sign-extended int32
values, preserving the reply. Fourteen per-process summary controls exercise
numeric bounds, excluded keys, string/data/nested-value exclusion and the
dictionary capacity. The [original-source patch](../patches/video-routing-v1-to-v2.patch)
reconstructs frozen v1 exactly; its old records are not rewritten or decoded
retrospectively.

The nine rotated cases share one raw executable, one executed signed executable,
libraries and invariant assets; only `dependency-choice.json` varies. The
positive changes one retained IOKit Boolean in our process. The XPC observer
itself changes no argument, reply, queue or handler. A passive positive retains
the local trace and failure without collecting native XPC records.

The qualified host's source body is unchanged, but its entry is renamed at
compilation: its object is **new**. Decoder/catalogue objects and the existing
entry, metadata and dependency libraries are reused exactly. No common Metal
runtime rebuild or new qualification of its historical matrices is implied.

## Boundaries and interpretation

The library observes three SDK-declared public APIs already called by our
frameworks: `xpc_connection_create_mach_service`,
`xpc_connection_send_message_with_reply_sync` and
`xpc_connection_send_message_with_reply`. Asynchronous handlers/queues remain
unchanged; their later replies are not observed.

Capture runs between explicit begin/snapshot calls for exact allowlisted
caller modules, with reentrant calls suppressed. Calls outside that lifetime,
from other modules or bypassing these symbols are out of scope. Zero records
do not prove no IPC exists. Only service names, bounded dictionary key/type
summaries and allowlisted numeric status/opcode fields are collected. String
values, binary values, nested contents, endpoints and video payloads are not
copied. Raw catalogues and object descriptions remain local.

The installed `VTDecoderXPCService.xpc` has the matching bundle identifier.
Its Info.plist SHA-256 is
`f18b8ec44bd3a65d03ae4ce25a7118903fe08dd7a5544994ace71d832372a9f3`;
its executable SHA-256 is
`a2b9bc6cf92cb58e06506d338c7363cde19303aee9b878730e20b73a69b4efbb`.
Those are **static bundle identities**, not live peer identification. The
running peer's executable, providers and registry observations are unverified.
Our local substitution does not modify another process's IOKit results. An
unchanged remote eligibility gate remains a hypothesis.

The 83 protected system files, additional video policy, OCLP and 36 common runtime
sources remain unchanged. No system service is injected or modified. No new
M1 execution, performance benchmark, hardware codec or extra Metal support is
claimed.

## Reproduction

This historical builder requires the frozen dependency build and its qualified
metadata/decoder objects, fixtures and runner from [VIDEO_DEPENDENCIES.md](VIDEO_DEPENDENCIES.md).
They are not vendor binaries distributed here. Public original sources are
exact; a clean clone has not regenerated the entire historical fixture chain.

Build off GPU, then inspect. Every run uses the existing shared laboratory
reservation root, including software/inspect runs. Output directories must be
new; a timeout is not authorization to replay a nonterminal process.

```sh
python3 bridge/tools/native_video_routing.py build \
  --dependency-build bridge/results/video-dependency-build-20261018-02 \
  --profile docs/video-routing-profile.json \
  --out bridge/results/video-routing-build-20261018-02

python3 bridge/tools/native_video_routing.py run \
  --build bridge/results/video-routing-build-20261018-02 \
  --codec H264 --mode inspect \
  --reservation-root "${KEPLER_LAB_RESERVATION_ROOT:?Set existing shared bridge root}" \
  --out bridge/results/video-routing-v2-inspect-20261018
```

Software controls use `--mode cpu` for H264/MPEG2Video, each in a new directory.
Hardware cases retain RequireHardware. The existing H.264 `both` dependency
variant also forwards EnableHardware. Nine balanced cases use `--codec H264
--mode hardware --routing observe` and `--override` in orders
`native,wrong-key,present-key`, `present-key,native,wrong-key`, then
`wrong-key,present-key,native`. Canonical archival names are
`video-routing-v2-<choice>-r<1..3>-20261018`. The audit reads those exact names:

```sh
python3 bridge/tools/audit_video_routing.py \
  --lab-root bridge --out bridge/results/video-routing-audit-new.json
```

It also needs historical local results, the reconstruction receipt and protected
file inventory; it launches no native program and cannot qualify a fresh clone
alone. Expected hardware errors are checked precisely and remain hardware
failures. An initial offline auditor used `-r` as a substring, accidentally
including the `video-routing` prefix; the corrected auditor selects exact planned
names. Its failed source/receipt remain local. No native test was replayed for
that bookkeeping correction.

Next: identify the live peer and its refusal path using bounded read-only
observations before designing an implementation. Real NVIDIA video submission,
CPU-correct hardware images, encoding, display, power, VRAM and wider Metal
requirements remain open.

Apple's [synchronous XPC contract](https://developer.apple.com/documentation/xpc/xpc_connection_send_message_with_reply_sync(_:_:)) specifies a retained service reply. [RequireHardware](https://developer.apple.com/documentation/videotoolbox/kvtvideodecoderspecification_requirehardwareacceleratedvideodecoder) makes session creation fail if hardware allocation fails and implies EnableHardware. Explicitly disabling [EnableHardware](https://developer.apple.com/documentation/videotoolbox/kvtvideodecoderspecification_enablehardwareacceleratedvideodecoder) supplies the software control. These contracts do not document the private opcode labels.
