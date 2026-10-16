# Observing the actual decoder registry

The new process-local observer records real CoreMedia registry calls in the
public H.264 and MPEG-2 requests. It identifies candidate descriptions and their
requirements. Adding both public hardware flags still produces **-12906 and
zero hardware images**. This is branch A investigation, not a hardware decoder
implementation, installed-driver correction or performance improvement.

## New evidence

| Cohort | Terminal processes | Result |
| --- | ---: | --- |
| Own known-ABI CPU calibration | 8 | 3,715 independently rechecked calls |
| Inspect without decoding | 1 | Six resident code hashes and image UUID match |
| Plain / entry observer, two codecs, CPU / hardware | 8 | 24 exact software images; four hardware failures |
| Public CF metadata observer, two codecs, CPU / hardware | 4 | 12 exact software images; two hardware failures |
| Public specification experiment | 4 | Six exact software images; three hardware failures |

All 25 processes use immutable signed executables and the shared host lease;
all are terminal and nonoverlapping. The software controls compare **42 images /
4,838,400 active NV12 bytes** with the existing independent FFmpeg CPU references,
with zero differences. These are repeated controls over the same six images per
codec, not 42 distinct test images. No new M1 execution was needed.

The [offline validation](video-registry-validation.json) rechecks source,
objects, libraries, signed executables, runner, lease and pixel provenance.
It also verifies 83 protected system files, the additional video policy file,
OCLP and 36 common runtime sources unchanged. System deployment, performance
benchmark and a causal IORegistry-dependency experiment are **NOT RUN**.

## What the observer does

One original x86_64 assembler object is shared by the calibration, plain and
observer libraries. Six entry tails record integer registers, entry stack,
flags and original return PC, restore the changed registers/flags and jump to
the original function. They contain no calls or vector/FP instructions. The
original return address and resident instructions stay unchanged. The host
never directly invokes an unknown private function or reads an opaque registry
item. These are qualified controls for the tested ABI cases, not certification
of every possible private interface.

Calibration forwards to our own known functions: 12 integer arguments, ten FP
arguments, a 24-byte indirect return, a mixed integer/FP return, variadic
arguments, all 64 arithmetic-flag patterns, saturation and disabled recording.
The saturation control deliberately produces 1,027 calls, 1,024 records and
three drops. Actual framework cohorts have no drops or pending records.

Before enabling observation, the host verifies CoreMedia **3330.13.105**, UUID
`7c4ae5aed528396982c6a4a534949ef3`, all six original symbol addresses and resident
code hashes against the [scalar profile](video-registry-profile.json).
The shared tail object SHA-256 is
`a95258db75c4f71923799fdafd2d62a9cb429488ac8a6236e08883679a51e877`.
Vendor function regions and disassembly are not distributed.

The second observer forwards the public `CFRetain` API unchanged. Only two
byte-pinned CoreMedia callers and an explicit known CF control are recorded.
It describes valid CF objects while they are alive, then preserves the original
ownership and result. The retain control releases the creator's reference and
checks the retained object's content before releasing that reference.
The metadata builds reuse the exact qualified host object, entry library and
tail; the specification builds also reuse the metadata implementation.

There are 663 real object captures across the eight metadata-enabled processes,
plus eight synthetic controls. All captures are complete and untruncated.
The offline auditor requires equal counts per entry-stack/index group before
associating each public retain capture with its framework entry. Raw pointers,
debug descriptions, pixels and process image catalogues stay private.
`CFCopyDescription` formatting is not a stable API and is not a production
decoder-selection contract. Observation also changes timing; these are not
benchmarks.

## What the recorded metadata says

| Implementation suffix | Relevant recorded information |
| --- | --- |
| `avc.vcp` | H.264 software-request path; rating 200 |
| `avd.avc` | Hardware flag; dependency `IOAVDHEVCDecodeCapabilities`; H.264 capabilities key |
| `h264.gva` | Hardware flag; dependency `IOGVACodec`; requires `EnableHardwareAcceleratedVideoDecoder=1` |
| `mpeg2` | Registered hardware flag is zero; codecs `mp1v` / `mp2v` |

These are candidate registrations observed in this OS, not proof that their
factories or hardware executed. Six read-only `ioreg -a -l -r -k KEY` queries
return no matching service for the recorded IOGVA/IOAVD keys. This is a
dependency clue; it does not establish that supplying a key would repair the
video transport.

The public specification experiment compares a passive wrapper, an unchanged
software request, and `RequireHardware=true` plus `EnableHardware=true`.
**RequireHardware remains true**. The actual forwarded dictionaries are recorded
separately from the original client's dictionary. Both H.264 and MPEG-2 still
fail before images. Enabling the additional flag alone is insufficient.

Actual hardware-failure traces observe one `FigSignalErrorAtGM` call with the
low 32 bits of its third integer argument register equal to -12906, returning
to VideoToolbox image offset 20163 in the inspected creation implementation.
This is more precise than the earlier static error-site hypothesis. It still
does not identify the rejection's cause. Zero interposed `GetFactory` calls
does not exclude direct, intra-image, cached or other unobserved calls.

## Reproduction

Use macOS x86_64 on the exact inspected profile, Xcode/SDK and Python 3.9+.
The original results used SDK 26.2 / clang 17. No system installation is needed.
Provide the two original thirteen-file fixtures, including independently
decoded references. See [H.264 staging](VIDEO_TRANSPORT.md#reproduction) and
[original MPEG-2 generation](VIDEO_CODEC_SELECTION.md#reproduction).

From `bridge`, choose new output paths. All native runners on a host must share
one reservation root. Set `SHARED_RESERVATION_ROOT` to that existing absolute
bridge path; on a new lab it can be this bridge directory.

```sh
python3 tools/native_video_registry.py build \
  --profile ../docs/video-registry-profile.json \
  --h264 /absolute/path/to/H264-fixture \
  --mpeg2 /absolute/path/to/MPEG2-fixture --out results/new-registry-build

for mode in integer floating aggregate mixed variadic flags overflow disabled; do
  python3 tools/native_video_registry.py run --build results/new-registry-build \
    --variant calibration --mode "$mode" --out "results/new-registry-$mode" \
    --reservation-root "$SHARED_RESERVATION_ROOT" || break
done

python3 tools/native_video_registry.py run --build results/new-registry-build \
  --variant H264-observer --mode inspect --out results/new-registry-inspect \
  --reservation-root "$SHARED_RESERVATION_ROOT"
```

Inspect the pins and completed calibration before running codec requests.
Use `H264-plain`, `H264-observer`, `MPEG2Video-plain` and
`MPEG2Video-observer`, each with `--mode cpu` and `--mode hardware`, serially
and with a fresh output directory. A completed diagnostic exit code is not a
successful hardware-decoder result. Check the decoded status and pixels.

```sh
python3 tools/native_video_registry_metadata.py build \
  --base-build results/new-registry-build --out results/new-registry-metadata-build
python3 tools/native_video_registry_metadata.py run \
  --build results/new-registry-metadata-build --codec H264 --mode cpu \
  --out results/new-registry-metadata-cpu --reservation-root "$SHARED_RESERVATION_ROOT"

python3 tools/native_video_registry_spec.py build \
  --metadata-build results/new-registry-metadata-build --out results/new-registry-spec-build
python3 tools/native_video_registry_spec.py run --build results/new-registry-spec-build \
  --variant H264-both --mode hardware --out results/new-registry-spec-hardware \
  --reservation-root "$SHARED_RESERVATION_ROOT"
```

Repeat with explicit distinct paths for the other controlled codec/mode pairs.
Keep original library paths intact: the sealed descendants reuse those exact
libraries. The historical CPU-only `audit_video_registry.py --lab-root
/absolute/path/to/original/bridge --out /new/audit.json` requires the omitted
private receipts, cache captures and pixels; a clean checkout cannot recreate
historical evidence merely from this JSON summary.

The first specification build's missing CoreMedia link dependency and the first
offline audit's empty-ioreg parsing error remain preserved in the lab. They
required no replay of a nonterminal process and are not counted as GPU failures.

Apple documents the public
[RequireHardware](https://developer.apple.com/documentation/videotoolbox/kvtvideodecoderspecification_requirehardwareacceleratedvideodecoder)
and [EnableHardware](https://developer.apple.com/documentation/videotoolbox/kvtvideodecoderspecification_enablehardwareacceleratedvideodecoder)
keys separately. These API references do not establish NVIDIA compatibility.

Next: trace the actual candidate-dependency decision and establish the GVA /
NVIDIA submission contract. Preserve the strict hardware requirement, software
oracle and failed controls; no global IORegistry or driver modification is
justified by these observations.
