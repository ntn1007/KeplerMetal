# Native decoder start and first pixel buffer

The native VideoToolbox start method now has runtime witnesses. Three final
same-executable current-board cases reach AppleGVA context setup and successfully
create its first CV pixel buffer: status0, non-null output. The final public
decoder creation still returns-12913 and produces **zero hardware images**.

The original-policy and wrong-board controls stop earlier at-12906. An allocated
pixel buffer or provider function table does not prove video-engine execution.
All hardware comparisons retain the earlier scoped `IOGVACodec` presence
counterfactual and strict hardware-required decoder specification. Current-board
cases additionally receive the copied board-policy entry only in process memory.
[Scalar audit](video-native-start-validation.json) ·
[Previous factory/policy experiment](VIDEO_FACTORY_POLICY.md)

## What is observed

The pinned native class/decoder table points to VideoToolbox offset4298704.
The2061-byte method has SHA-256
`f3cb75d0d4d4c97e2ca66ed815bd0fa636d96f6c955ba98d0fe8be39860a7a60`.
Its loaded bytes are checked before observing these public calls:

| Witness | Native return offset | Current-board cases | Negative policy cases |
| --- | ---: | --- | --- |
| CFBundle resolves `AVFQTX_GetMaxParsedStructureVersion` | VT4298852 | Real AppleGVA pointer at5332 | No call |
| CFPreferences reads `H264GVAPixelFormat` | VT4299460 | Original null result preserved | No call |
| CVPixelBufferPoolCreatePixelBuffer | AppleGVA263397 | Status0 / non-null | No call |

The preference lies after a successful formats query in the inspected native
method. No preference is written or substituted. User/host preference values
are not collected. The CV observer reads the typed output slot only after a
successful call; it reads no resource contents and changes no ownership.

Public `backtrace` observations distinguish the actual policy callers:

| Policy read | AppleGVA caller return | VideoToolbox caller return |
| --- | ---: | ---: |
| Factory availability | 260915 | 4294967 |
| Output formats | 280947 | 4299346 |
| Context setup | 262414 | 4300698 |

All pass through the pinned AppleGVA policy query at return722786. Four recorded
current-board hosts include these three complete stack sequences. V7/V8 also
hash-pin the loaded GVA format/dimensions/context functions. The observer never
calls those private functions directly or replaces a native method or table.
The previously documented GetFactory caller-return-address limitation remains.

The format function at280889 is105bytes, SHA-256
`496574a0765c6a36c756d3c1ca750a670d358b5d8a9d559d1f51e590a7ca335f`.
The dimensions parser at260544 is315bytes, SHA-256
`27eddfec94f057db30d6dfd5a1578db71138bc238ad197c08893ba4ef1672bb4`.
Context setup at262270 is2452bytes, SHA-256
`2ce45fe6c3ffc591e794e46655393ba2848540f55c891bfbf1f189e6d0e4c9e0`.
These identities qualify observations on AppleGVA10.0.20 / UUID
`ca5414f369373c059ea2d82b35afd4f0`; they are not generic ABI certificates.

## Cohort and limits

Seventeen new immutable signed hosts are terminal and nonoverlapping: five V6,
two V7 and ten V8 cases. There are18 exact software images /2,073,600 active
NV12 bytes and1952 mock argument/errno/status/output checks. Five current-board
hosts witness native start; four include the context caller stack; three V8
hosts observe the successful first pixel buffer. The final seven hardware
policy comparisons use the same original executable.

All11 hardware creates remain refused: six at-12906, five at-12913. The three
software hosts retain12 nonzero FinF/Inva replies at-12782. Full service lifetime
is still unqualified. Completing this diagnostic does not make those internal
errors successful. No video-engine submission or hardware output is proved.

The earlier19-host factory audit remains byte-identical. Both published and
laboratory auditors recheck the new cohort, all pixel bytes and frozen inputs.
The83 protected components, both policies, OCLP,36 common runtime sources and
common archive remain unchanged. No new M1 run, full Metal suite, benchmark,
performance gain or installed-driver change is claimed. BranchB gains no new
Metal feature in this branchA diagnostic milestone; the full goal is incomplete.

## Next boundary

Static analysis shows that the508-byte provider constructor at AppleGVA4824
allocates a CPU-side function table and returns0. That alone is not GPU context
creation. Its session slot+0xf0 points to115359, a719-byte dispatch region that
selects a codec handler and requests an output count. Its failing runtime
branch has **not** been observed. The next task is to trace that candidate enumeration
and its actual public registry/IOKit dependencies after the first pixel buffer.

REA6.4.0 / Ghidra12.1.4 corroborates the2452-byte context region in a derived
ELF container. Its recovered body is2423bytes with bad-instruction/coverage
warnings; no complete private ABI is inferred. Inline jump-table data and
unavailable external targets must not be mistaken for native execution faults.
Private captures, disassembly, stacks containing unrelated images and analysis
bundles are not published.

`map_video_stub_targets.py` is an original, execution-free helper for the earlier
cache-symbol problem. It verifies a six-byte RIP-relative GOT stub, requires a
slide-v2 rebase-chain member, maps the exact target image and scans nlist in
4096-entry pages. It reads only bounded strings rather than the107MB shared
string table. It records **static** targets and never promotes them to runtime
call proof. The context and session inspections map27/18 callsites through13/11
unique stubs, respectively; unmatched exact symbol names remain unknown.

## Reproduction

Use the existing frozen laboratory prerequisites and the shared reservation
root from [the factory experiment](VIDEO_FACTORY_POLICY.md). No proprietary
components are distributed; see [dependency recovery](DEPENDENCIES.md).

Build a new directory, inspect first, then run the software/original-policy/
wrong-board/current-board sequence already documented there. The current source
automatically adds the public start, preference, stack and CV observations.
Never overlap runs or retry a nonterminal process. These source builds use
x86_64 SDK26.2 / Apple clang17.0.0 (`clang-1700.6.4.2`), C++17, blocks and MRC
on macOS26.7.1 /25G241; unchanged earlier objects retain their own provenance.

`patches/video-start-v8-to-v{5,6,7}.patch` reconstructs earlier observer/builder
text. Eight text comparisons pass. For older factory versions, first reconstruct
V5, then use its existing V5-to-V1/V2/V3/V4 patches. This is source reconstruction,
not a claim that a new build inherits the frozen artifact's qualification.

Historical auditing executes no native program and expects the exact dated
cohort directories listed in its source:

```sh
python3 tools/audit_video_start.py --lab-root . --out results/start-audit-new.json
```

An explicit static cache inspection can be mapped without loading vendor code:

```sh
python3 tools/map_video_stub_targets.py --cache "$CACHE" \
  --analysis results/video-gva-start-interface-analysis-20261018/analysis.json \
  --record 1 --out results/context-static-targets-new.json
```

`CACHE` must be the explicit local cache used by the bounded inspection. The
helper requires fresh output and validates its capture metadata and hashes.
