# Video service identity and its native selection path

The replying peer is now observed through public XPC PID queries and two
read-only birth/path queries around each path lookup. Fourteen observations
cover seven distinct process births. Two independent, bounded unified-log
windows corroborate the service image path, its x86_64 UUID and its connection
to our exact test client. Hardware decoding still fails before images.

This is branch A investigation, extending [video routing](VIDEO_ROUTING.md).
No installed driver, system service or Metal API is changed. The wider hardware
goal remains incomplete.

## New executions

| Cohort | Host runs | Outcome |
| --- | ---: | --- |
| Inspect | 1 | No decoder request or native XPC capture |
| H.264/MPEG-2 software controls, including final H.264 | 3 | 18 exact images / 2,073,600 active NV12 bytes |
| Initial positive hardware probe | 1 | Two consistent peer observations; hardware refusal |
| Native and wrong-key hardware controls | 2 | No observed decoder-service exchange |
| Peer observation on/off, three repeats each | 6 | Same binary, unchanged service replies and hardware failure |

All **13** signed hosts are terminal, nonoverlapping and use the original shared
reservation. The [source-only auditor](../bridge/tools/audit_video_peer.py) and
[recorded audit](video-peer-validation.json) verify **1,248 mock ABI/errno calls**,
**182 bounded-summary controls**, **260 PID/birth/path controls**, **269 native
XPC records**, **18 actual GPU property queries**, **24 public query controls**,
**120 dependency scope checks** and **1,639 CF metadata associations**.

The 260 peer controls comprise 19 pure predicate cases and one real own-process
metadata control per host. They do not race live PIDs or inspect unrelated
processes. The 32 mock triples per host check incoming and outgoing errno, all
arguments, returned object identity and asynchronous handler/queue identity.
Mock callbacks execute locally; this is not native asynchronous qualification.

All **nine hardware-required creates remain -12906 / zero images**. The presence
experiment remains scoped to our own IOKit returns. Software controls use the
existing independent CPU references, with zero differences. No new M1 run or
performance benchmark was performed. The old 19-host routing audit is rechecked
without GPU replay and produces an identical report.

## Peer observation and limits

The observed executable path is:

```text
/System/Library/Frameworks/VideoToolbox.framework/Versions/A/XPCServices/VTDecoderXPCService.xpc/Contents/MacOS/VTDecoderXPCService
```

Its installed universal file has SHA-256
`a2b9bc6cf92cb58e06506d338c7363cde19303aee9b878730e20b73a69b4efbb`.
The observed x86_64 UUID is `1cfa17825c4533bdbe30d374732a91c5`; a separate
arm64e slice is present but is not the observed Intel process.

After the two named reply exchanges, `xpc_connection_get_pid` is queried before
and after `proc_pidinfo` / `proc_pidpath` / `proc_pidinfo`. Complete BSD metadata,
matching PID/UID/birth values, a bounded terminated path and a birth predating
the reply timestamp are required. Both exchanges agree on the process birth.
The API's [PID-reuse warning](https://developer.apple.com/documentation/xpc/xpc_connection_get_pid(_:)) still applies: these checks establish consistency and corroboration, not cryptographic authentication or complete exclusion of PID reuse and clock races.

Metadata is read only for the named decoder service and `uber`/`Strt` exchanges.
The observer preserves the errno seen by the original call and the errno it
returns, including after logging/pool drainage. `--peer passive` disables peer
queries while retaining the ordinary XPC observer. In six crossover processes,
only `peer-choice.json` changes; the signed executable, libraries and all other
assets are identical. Every case still replies `uber=0`, `Strt=-12906`.

The `own_process_only` field describes where our interposition code runs.
The new public libproc queries do read the replying process's kernel metadata;
they do not read its memory, inject code, alter callbacks in it or modify it.
Raw PID/birth records and logs remain private. The public audit contains selected
counts, image identifiers and hashes.

The two log windows contain 36 software and 27 hardware records, filtered to the
recorded process/path and host-run interval. They corroborate the peer/client
connection. Some message content is privacy-redacted; no privacy setting is
changed or redaction bypassed. Logs do not prove the internal refusal cause or
a complete inventory of loaded providers.

## Static native path

REA 6.4.0 with Ghidra 12.1.4 analyzes a private x86_64 slice derived from that installed
file, SHA-256 `9b1a189d3f9dba534cadfe44e852b3740227471f890ee94ae012856689e01612`.
Evidence `ev_63ad658ae6dc86220b197dcba7812bbaa15f9db653fa28ec035b18101a832b1a`
records the 16-byte entry at `0x100000578`: it passes the imported
`VTRemoteDecodeServer_XPCServiceConnectionHandler` pointer to `xpc_main`.
An independent native import inventory agrees. No annotations or original
binary edits are made; the analysis session is closed with private evidence
and snapshot files retained.

Bounded cache captures and LLVM analysis then establish this **static** chain
inside VideoToolbox 3330.13.105 / UUID `e7231bea63883d0a95c0a93ce970b96b`:

| Role | Image offset | Captured bytes |
| --- | ---: | ---: |
| Exported connection handler | 4268444 | 101 |
| Its block callback | 4268545 | 14 |
| Event dispatcher | 4268559 | 140 |
| Message dispatcher containing `Strt` | 4269743 | 6,156 |

The `Strt` comparison reaches a block with a call at **4272141** to **6288668**,
the decoder selector already captured in the earlier investigation. Its
2,234-byte hash remains `6b98a81482d8cce93ec6e651d4828edf574af91e6468b8436c484952da35d5ee`.
A nonzero return from that call is copied into the signed status sent in the
reply. Other paths also exist. This locates a candidate repeated selection
step; it does **not** prove that this branch produced the observed remote
-12906 or that a second missing-property query is the complete root cause.
No private callback or new private ABI is invoked by our host.

The SDK declares `xpc_connection_handler_t` as a function taking one
`xpc_connection_t` and returning void. Together with the native entry, that
constrains the callback slot; the full initialization/lifetime contract for
using the native callback in a new helper is not yet qualified.

Only hashes, offsets, names and bounded conclusions are published. Vendor
instructions, decompiler bodies, cache fragments, universal/thin executables,
raw logs and private object catalogues are not distributed.

## Reproduction and next experiment

The original builder now emits observer schema3. Older routing results belong
to source commit `22920b5`; [our source patch](../patches/video-routing-v2-to-v3.patch)
reconstructs frozen v2 in a separate checkout. Frozen results are never edited.
The underlying qualified dependency build and fixtures remain prerequisites;
a clean clone has not regenerated that whole historical chain.

```sh
python3 bridge/tools/native_video_routing.py build \
  --dependency-build bridge/results/video-dependency-build-20261018-02 \
  --profile docs/video-routing-profile.json \
  --out bridge/results/video-peer-build-20261018

python3 bridge/tools/native_video_routing.py run \
  --build bridge/results/video-peer-build-20261018 \
  --codec H264 --mode inspect --peer observe \
  --reservation-root "${KEPLER_LAB_RESERVATION_ROOT:?Set existing shared bridge root}" \
  --out bridge/results/video-peer-inspect-20261018
```

Use a new directory and the same reservation for each software/hardware case.
The crossover uses `--codec H264 --mode hardware --override present-key`, with
`--peer observe` or `--peer passive`; no hardware requirement is removed.
The historical auditor also needs the canonical recorded cohorts, log receipts,
static private artifacts and original protected-file inventory:

```sh
python3 bridge/tools/audit_video_peer.py \
  --lab-root bridge --out bridge/results/video-peer-audit-new.json
```

The first audit development attempt used Python3.9's incompatible ISO parser
for log offsets such as `+0200`; explicit `%z` parsing fixes that reader. The
failed source/receipt are retained, with no native replay. Static metadata
initially showed a universal executable; the analyzed slice is explicitly
selected rather than assuming the original file was thin.

The 83 system files, video policy, OCLP, 36 common runtime sources and archive
`5636b0d0…` remain unchanged. Next: qualify a public anonymous XPC listener's
lifecycle before considering an isolated native-handler experiment. A local
helper would be a laboratory integration step; it would not satisfy transparent
driver support. Hardware video submission/correct images, encoding, display,
power, VRAM and remaining Metal requirements stay within the full goal.
