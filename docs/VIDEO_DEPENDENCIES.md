# Native GPU dependency: observed and tested in one process

VideoToolbox really asks the GTX 880M's `nvAccelerator` for `IOGVACodec` and gets
no object. A tightly scoped, process-local presence substitution changes the
decoder-selection path in three fresh processes. It still does **not** create
a hardware decoder: all hardware requests return **-12906 with zero images**.

This is a causal selection experiment in branch A, not an installed driver
repair, a hardware capability declaration or a new Metal feature.

## Evidence and scope

| New cohort | Processes | Outcome |
| --- | ---: | --- |
| Initial public-API observer, including inspect | 8 | 18 exact software images; four hardware failures |
| Revised inspect and software control | 2 | Ten scope checks per process; six exact software images |
| Native / wrong-key / present-key comparison | 9 | Three repeats per choice; hardware failure retained |

All 19 processes are signed, terminal, nonoverlapping and use the original
shared host reservation. The four software controls compare **24 images /
2,764,800 NV12 bytes** against the earlier independent FFmpeg CPU references,
with zero differences. They reuse the six original images per codec; no new
M1 execution or general codec-conformance claim is made.

The [offline audit](video-dependency-validation.json) verifies executable,
source, object, library, runner, lease and image provenance. It checks 38 public
query controls, 110 pure CPU scope checks, 22 real property queries and 1,706
real CF metadata associations. The protected 83 system files, additional video
policy, OCLP and 36 common runtime sources remain unchanged. The common Metal
runtime is neither rebuilt nor replaced by this experiment.

The refreshed machine observation is still iMac11,1, i7-870, 32 GiB, macOS
26.7.1 / 25G241, PCI NVIDIA device 0x1198 and 8 GB VRAM. These observations do
not certify extra Metal generations or hardware video execution.

## Actual property queries

The added library forwards the documented, retained-return public API
`IORegistryEntrySearchCFProperty`. It records only an explicit control and one
resident-pinned VideoToolbox caller, image return offset **6285217**. The public
SDK header defines the five arguments and the caller's release obligation.
The observer does not guess a private signature or read an opaque registry
item. Query arguments, results and ownership stay unchanged in native mode.

The host verifies five complete function regions in VideoToolbox
3330.13.105, UUID `e7231bea63883d0a95c0a93ce970b96b`, before activating. The
unchanged codec host independently checks the six CoreMedia functions from the
[earlier observer](VIDEO_REGISTRY.md). The qualified host, decoder objects,
entry library and CF metadata library are reused exactly.

Actual H.264 hardware queries use `IOService`, recursive options 1, and
`nvAccelerator` registry ID **4294968458**, matching this GPU's Metal identity:

| Key | Original result |
| --- | --- |
| `IOGVACodec` | Absent |
| `IOAVDHEVCDecodeCapabilities` | Absent |

The earlier empty `ioreg` searches were only clues. These new records establish
what this VideoToolbox path actually requests from the NVIDIA service. They
do not turn an absent property into proof of missing physical hardware.

## Controlled presence experiment

All nine compared processes use the same raw executable, the same libraries
and the same executed signed executable, SHA-256
`93b3499c593d94edc846bcd842e1e1d84d2f4511067bfb9b7fbf73b7d051dc14`.
Only the original `dependency-choice.json` asset varies. Each repeat uses a new
process; the three choice orders are rotated to avoid a fixed ordering effect.

| Choice | Changed returns per process | Entry observations | Error return offsets in VT | Hardware images |
| --- | ---: | ---: | --- | ---: |
| `native` | 0 | 87 | 20163 | 0 |
| `wrong-key` | 0 | 87 | 20163 | 0 |
| `present-key` | 1 | 178 | 6290187, 20163 | 0 |

The positive substitutes a retained public Boolean for one original null
result. It requires the exact native caller, exact GPU registry ID,
`IOService` recursive lookup, exact `IOGVACodec` key, original absence, and an
explicit request containing **RequireHardware=true and EnableHardware=true**.
The wrong-key control exercises the same code with a key the native query does
not request. Ten CPU checks cover the allowed case and refusals for native
mode, wrong key/caller/GPU/plane/options, software scope and an existing result.
The `IOAVDHEVCDecodeCapabilities` result is never replaced.

The returned Boolean preserves the public API's retained ownership. The
returned value deliberately changes in the positive test; the system
IORegistry does not change. This is a counterfactual eligibility test, not a
production capability adapter. Setting a presence bit does not implement a
decoder or certify backend compatibility.

Correlated CF descriptions show the `h264.gva` candidate reaching the creation
loop at return offset **6289206** only in the positive cases. An additional
-12906 signal appears at **6290187**, before the public creation error at
20163. This establishes a selection barrier, not the sole cause of failure.
Zero interposed `GetFactory` calls still does not exclude direct, intra-image
or cached calls. No factory execution is inferred from those zero counters.

AppleGVA is absent from our own recorded image catalogues. No other process or
XPC service is inspected, so this says nothing about providers loaded elsewhere.
The next 450-byte creator region, offset **2630814**, is inspected statically
and references `UseRosettaService`. That is a routing investigation target;
neither invocation of that helper nor a remote decoder is proved here.

## Reproduction

This source snapshot is intentionally restricted to the inspected x86_64
profile and GPU identity. A different machine/profile requires separate
qualification, not automatic repinning. Use Xcode/SDK and Python 3.9+; the
original builds used SDK 26.2 / clang 17. Proprietary cache bytes, disassembly,
pixels and raw process catalogues are omitted.

First build and qualify the registry/metadata artifacts and independent
fixtures as described in [VIDEO_REGISTRY.md](VIDEO_REGISTRY.md#reproduction).
From `bridge`, use a new directory for every operation and the same absolute
`SHARED_RESERVATION_ROOT` used by all native lab runners on the host:

```sh
python3 tools/native_video_dependency.py build \
  --metadata-build results/qualified-registry-metadata-build \
  --profile ../docs/video-dependency-profile.json --out results/new-dependency-build
python3 tools/native_video_dependency.py run --build results/new-dependency-build \
  --variant inspect --mode inspect --out results/new-dependency-inspect \
  --reservation-root "$SHARED_RESERVATION_ROOT"
python3 tools/native_video_dependency.py run --build results/new-dependency-build \
  --variant H264-both --mode cpu --out results/new-dependency-cpu \
  --reservation-root "$SHARED_RESERVATION_ROOT"
```

Check the controls, pins, exact pixels and actual terminal state first. Then
run the three choices serially with distinct output directories:

```sh
python3 tools/native_video_dependency.py run --build results/new-dependency-build \
  --variant H264-both --mode hardware --override native \
  --out results/new-dependency-native --reservation-root "$SHARED_RESERVATION_ROOT"
python3 tools/native_video_dependency.py run --build results/new-dependency-build \
  --variant H264-both --mode hardware --override wrong-key \
  --out results/new-dependency-wrong --reservation-root "$SHARED_RESERVATION_ROOT"
python3 tools/native_video_dependency.py run --build results/new-dependency-build \
  --variant H264-both --mode hardware --override present-key \
  --out results/new-dependency-present --reservation-root "$SHARED_RESERVATION_ROOT"
```

The CLI refuses a non-native choice outside `H264-both` hardware mode. Preserve
failures and stop for inspection on a changed outcome; exit zero only indicates
a completed diagnostic. Do not infer hardware use from a selected candidate or
a successful session creation. Require engine identity and correct images.

The [original-code patch](../patches/video-dependency-v1-to-v2.patch), applied
in reverse to a disposable source copy, reconstructs the two earlier v1 files.
Their hashes are independently checked against the frozen v1 sources. The
historical offline `audit_video_dependency.py --lab-root /absolute/path/to/the/
original/bridge --out /new/audit.json` needs the omitted private receipts and
captures; a clean checkout alone cannot recreate their evidence.

Next: observe the framework's creation/routing path after GVA selection,
including any provider or proxy boundary. Keep the hardware requirement and
failed controls. No system deployment, new video engine implementation,
performance benchmark or complete-hardware support is claimed.
