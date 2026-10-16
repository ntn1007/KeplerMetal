# Video transport investigation

The current macOS video APIs still produce no hardware-decoded image on the
reference GTX 880M. This branch A investigation narrows the transport search;
it adds no codec, Metal feature, installed driver or performance improvement.

## Findings

The installed native `GeForceVADriver` and the original NVIDIA Web Driver
387.10.10.10.40.140 each contain only two 11-byte factory bodies, returning the
private constant 14. The WebVA extracted from NVIDIA's original installer is
byte-identical to the inspected Dortania support copy. The installed native VA
also matches its separate Monterey support copy. Their identities and exact
source revisions are recorded in [the validation summary](video-transport-validation.json).

These entrypoints supply no accelerator implementation. This does **not** show
that VideoToolbox called them, explain its error, or exclude another AppleGVA
route. The private value 14 is not mapped to a public API error. Copying this
WebVA would not supply an implementation through those exports.

The official package's installer certificate is expired according to the local
`pkgutil --check-signature` result. Only archive members were extracted; no
installer or package script was run. The original package and all vendor code
stay outside this repository.

## Executed controls and observations

| Check | Result | Scope |
| --- | --- | --- |
| Tail-observer calibration | 768 correct ABI cases across three frozen observer versions | Synthetic CPU functions; integer/stack and floating-point/stack arguments |
| Public legacy VDA | Six failed creates, `-12473` | Same valid H.264 fixture; plain and observed in three builds |
| Independent software decode | Six exact images, 691,200 active NV12 bytes, zero differences | iMac VideoToolbox with hardware disabled versus existing FFmpeg 9.0.2 on arm64 with `-hwaccel none` and native H.264 decoder |
| Public VideoToolbox hardware requirement | Both plain and observed creates fail `-12906`; zero images | Same compressed fixture and final immutable executable |
| IOKit observation | Six events, including native clients 5/6 and Metal initialization stacks | Own process; no video-engine submission established |
| Monitored AVD factory calls | Zero | Only the declared post-activation lookup paths are observed |

All 13 probe processes have terminal receipts, with nonoverlapping intervals and
the original shared laboratory reservation root. Exit code zero records a
completed diagnostic, not working hardware video. The final observer freezes
its recording before constructing its snapshot; older versions retain their
original snapshot behavior and are audited separately.

The first iMac software control decoded six images but lacked comparison
files. That incomplete result remains intact. The next build stages only the
independent reference assets; its executable, observer and native objects are
identical to the preceding build. It still loads the observer at the original
frozen library path. New process results were collected, not inherited.

The software session's `UsingHardwareAcceleratedVideoDecoder` query returns
`-12900` and null. It is not interpreted as false; the explicit decoder
specification disables hardware under Apple's documented contract. Pixels are
checked independently from saved output files. The reference qualifies image
content/order for this bitstream, not timing or general codec conformance.

## Observation boundaries

The linked observer forwards public IOKit calls unchanged. For two narrowly
matched vendor symbol lookups it can return an ABI-neutral counting tail that
jumps to the original pointer. The host never constructs an unknown vendor
call. No vendor tail was selected in the actual VDA/VT observations.

The trace does not cover cached or pre-main symbol resolution, direct/private
lookup mechanisms, every IOKit API, or another process. `dladdr` supplies the
nearest exported symbol; a symbol name is not proof of an exact function
boundary. IOSurface selector 44 also occurred in earlier successful Metal
traces, so its status is not assigned as the video failure's cause.

Read-only registry inspection finds `IOVARendererID` 0x01040008 and sub-ID 3
already present. WhateverGreen's missing-property fix therefore does not justify
an installation or registry edit here. Its source is a research reference, not
a qualified Tahoe fix. Historical AppleGVA 10.13.6 has NVIDIA renderer branches;
it was inspected offline and was not loaded or executed.

## Reproduction

The source-only export includes the original probe, observer, builders, runner,
reference stager and auditor. Historical fixtures and binary evidence are
omitted. First regenerate or obtain a local valid six-frame 320x240 H.264 AVCC
fixture: seven files comprising `fixture.json` and six AVCC frames, including
SPS/PPS and frame timestamps in the metadata. The asset-only staging route
expects no existing `cpu-frame-*.nv12` references in that source build. The audit below
requires the named original laboratory evidence; a fresh checkout cannot
recreate historical hashes from the summary.

From `bridge`, use a **new** output directory for every build and run:

```sh
python3 tools/build_video_va_observer.py \
  --fixture /absolute/path/to/fixture --out results/video-observer-build
python3 tools/run_video_va_observer.py \
  --build results/video-observer-build --out results/video-observer-selftest --mode selftest
```

Produce an independent CPU reference from a payload-preserving Annex-B form of
the same SPS/PPS and AVCC NAL units, on a machine with FFmpeg already available:

```sh
ffmpeg -hide_banner -nostdin -n -loglevel verbose \
  -hwaccel none -c:v h264 -threads 1 -f h264 -i fixture-annexb.h264 \
  -filter_threads 1 -filter_complex_threads 1 -an -sn -dn -frames:v 6 \
  -c:v rawvideo -pix_fmt nv12 -threads 1 -f rawvideo decoded.nv12
```

Record the FFmpeg version, binary/input/output hashes and actual terminal
result; verify hashes after an explicit authorized transfer. The published
auditor reconstructs Annex-B from the saved AVCC payloads. The downloaded
FFmpeg 7.1.5 source was not built or used as this experiment's reference.

```sh
python3 tools/stage_video_cpu_references.py \
  --source-build results/video-observer-build --reference /absolute/path/to/decoded.nv12 \
  --reference-sha256 YOUR_VERIFIED_SHA256 --out results/video-observer-referenced
python3 tools/run_video_va_observer.py \
  --build results/video-observer-referenced --out results/video-observer-cpu --mode vt-cpu
```

Verify all six images against the independent CPU output before proceeding.
Then run `vt-plain` and `vt-observe` serially with distinct output directories,
checking actual termination between them. `plain`/`observe` select legacy VDA.
The strict host pin intentionally refuses a different installed VA. Keep the
original library path intact when using the asset-only stager.

CPU-only re-audit of the existing private laboratory:

```sh
python3 bridge/tools/audit_video_transport.py \
  --lab-root /absolute/path/to/existing/bridge --out /absolute/path/to/new-audit.json
```

## Remaining work

Establish the actual AppleGVA/decoder registration and NVIDIA video submission
contract, then implement or reconnect a viable transport in an isolated process.
A successful session must produce hardware images checked against the CPU and
provide engine/driver attribution. Encoding, other codec modes, performance,
transparent application integration and the full hardware objective remain open.

## Primary references

- [NVIDIA original macOS Web Driver](https://www.nvidia.com/download/driverResults.aspx/167083/1000/) and [dependency recovery](DEPENDENCIES.md).
- [Dortania support revision](https://github.com/dortania/PatcherSupportPkg/tree/3250ca07ca49e3f8c743066381b5688028681de8).
- [Apple hardware-disable decoder specification](https://developer.apple.com/documentation/VideoToolbox/kVTVideoDecoderSpecification_EnableHardwareAcceleratedVideoDecoder) and [hardware-required specification](https://developer.apple.com/documentation/VideoToolbox/kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder).
- [WhateverGreen renderer-property implementation](https://github.com/acidanthera/WhateverGreen/blob/093e76fec5655001f38b367dd22459c756ee89fa/WhateverGreen/kern_ngfx.cpp#L270) and [historical renderer compatibility](https://github.com/acidanthera/WhateverGreen/blob/093e76fec5655001f38b367dd22459c756ee89fa/WhateverGreen/kern_shiki.cpp).
