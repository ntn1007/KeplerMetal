# Native video factory and AppleGVA policy

The native factory loader succeeds. The remaining hardware refusal is farther
along the decoder path. Seven fresh processes running the **same executable**
isolate a second eligibility policy inside AppleGVA:

| Process-local policy | Processes | Actual policy reads | Native `Strt` / public create | Hardware images |
| --- | ---: | ---: | ---: | ---: |
| Original table | 2 | 1 each | -12906 | 0 |
| Existing profile copied under an absent, wrong board key | 2 | 1 each | -12906 | 0 |
| Same profile copied under this iMac's board key | 3 | 3 each | -12913 | 0 |

This establishes a causal policy barrier and a changed native path. It does
not establish working hardware decoding. All seven cases retain the public
`RequireHardwareAcceleratedVideoDecoder=true` requirement and use the earlier
owned native transport and scoped `IOGVACodec` presence experiment. Only the
policy choice asset differs among these seven cases.

[Scalar audit](video-factory-policy-validation.json) ·
[Previous native transport](VIDEO_LOCAL_SERVICE.md)

## What the factory observation proves

CoreMedia3330.13.105 / UUID `7c4ae5aed528396982c6a4a534949ef3` contains the
173-byte `FigRegistryItemGetFactory` at image offset135509, SHA-256
`57a7ef8a79a22ba025e1bd3b14c42c3462ca92db447ff9c6efeead2a98c55a16`.
Its complete machine body and caller establish three arguments: opaque item,
32-bit load flag, and writable factory-pointer output slot; the result is a
32-bit status. Existing calls are forwarded with the recovered ABI. The
observer never dereferences the opaque item or invokes the returned factory.
There are512 mock forwarding controls across the recorded hosts; these are
ABI/errno/output-slot checks, not hardware execution.

In the recorded hardware cases, the natural loader returns status0 and a
non-null pointer into VideoToolbox at offset4294856. The nearest `dladdr`
symbol is at4277198 and **is not the factory's name**. The pinned523-byte
factory, SHA-256
`790c12ecc76f4959aa7db7047075e763e82d58819b54dc86c4ecc2d08fd002df`,
resolves `AVFQTX_CreateMediaAcceleratorInterface` through the public CFBundle
API. Its actual result is AppleGVA10.0.20, UUID
`ca5414f369373c059ea2d82b35afd4f0`, exact offset4577.

The software path instead resolves the exact
`H264VideoDecoder_CreateInstance` in AppleH264SW, UUID
`85e6e70880dd3ccb9c8c31e2d40f812a`, offset25296. This is an MH_BUNDLE without
LC_ID_DYLIB; its absence of an install version is legitimate. V1's missing
target metadata is preserved, and later observers handle this case explicitly.

The natural private forwarder changes the original function's immediate caller
return address. It is not a fully transparent ABI observer. Inputs, typed output
slot, status and errno are preserved; no returned function is called by our
observer. Runtime/profile checks refuse mismatched versions and hashes.

## The second policy is distinct from AppleVA

This experiment reads the installed AppleGVA `Resources/Info.plist`, SHA-256
`c7cefb08fe12c1da168d8baad6b92d341ff3e331a4d2c5011de5d36bff64b3e3`.
Its `System Support` dictionary has neither `Mac-F2268DAE` nor `iMac11,1`.
It is a separate file and gate from the earlier AppleVA/AppleVADriver VP3 test.

Static bounded analysis maps the interface's availability slot+0x30 to the
62-byte AppleGVA function at260870, which calls the1192-byte query at722087
(SHA-256 `365f8095e2d41076df73fec998db936f6518ce04b21ffdf62a9765fc646670be`).
The real public `CFDictionaryGetValue` at return offset722786 is observed only
after the pinned interface is naturally resolved. The returned original table
must equal the independently parsed installed table and lack the current board.

The counterfactual returns a process-owned copy, adding
one key whose value is the **unchanged existing** `Mac-27ADBB7B4CEE8E61` profile.
The wrong-board control adds the same value under a key this machine never
looks up. The original dictionary and installed file remain unchanged. A
process-lifetime owner preserves the public getter's borrowed-return contract.
This reference profile is not a hardware compatibility certificate.

Three current-board cases additionally record a -12900 error at VT return
offset4275288, in the indirect `DecoderProducesRAWOutput` property query. The
native `Strt` reply and final public create are -12913. The property query's
return is not used as the final `Strt` result in the inspected path; its error
must not be presented as the cause of the final refusal. The decoder's actual
start method and its next AppleGVA/NVIDIA dependency remain to be observed.

## Qualification and retained limitations

The cohort has19 immutable, signed, terminal, nonoverlapping host processes:
four inspections, five software decodes and ten hardware refusals. The software
cases produce30 images /3,456,000 active NV12 bytes, all identical to the
independent CPU reference. There are608 public resolver mock controls and512
GetFactory mock controls. One failed V2 link remains preserved; no native host
in this cohort crashed or required SIGKILL.

The host is x86_64 macOS26.7.1, build25G241. New compilation uses SDK26.2 and
Apple clang17.0.0 (`clang-1700.6.4.2`), with baseline x86_64, C++17, `-O2`,
blocks and MRC. The existing transport objects/libraries are hash-verified and
reused; their own original toolchain provenance is retained separately.

The five software cases also retain20 nonzero native replies: three `FinF`
and one `Inva` at-12782 per process. The public sample outputs and public
finish/wait results pass, but these internal replies are **not** declared
successful. Full native service initialization and lifetime remain unqualified.

The auditor rechecks input/source/object/library hashes, signed executables,
shared reservations, raw replies and error sites, metadata bijections and all
pixel bytes. The exported auditor produces an identical report against the lab
tree. Its PASS means the scoped observations match their expected outcomes;
hardware decoding is still unsuccessful.

REA6.4.0 / Ghidra12.1.4 corroborates the factory ABI and retains analysis
Evidence. The later6156-byte event-handler container gives a6123-byte Ghidra
body with bad-instruction/PIC warnings. That partial dossier is not proof of a
complete private ABI. Vendor captures, disassembly, raw IPC and analysis bundles
remain private; the repository contains original source, hashes and conclusions.

A cache-inspector bug previously treated a defined nlist symbol at indirect
index0 as an import name. The corrected parser accepts only N_UNDF|N_EXT for
that name. Six portable synthetic tests pass; three assertions failed on the
previous parser. A verified static GOT example resolves to `malloc_type_calloc`,
not the previously reported defined accelerator symbol. Historical analyses
are preserved and a corrected three-region analysis is stored separately.

The83 protected components, AppleVA and AppleGVA policies, OCLP,36 common
runtime sources and common archive are unchanged. This milestone adds a branchA
diagnostic capability, no branchB Metal feature. No benchmark, speedup, new M1
execution or global driver installation is claimed. The full hardware goal is
incomplete.

## Reproduction in an existing laboratory tree

The later [native-start observer](VIDEO_NATIVE_START.md) is the current source.
First apply its V8-to-V5 patch when reconstructing this milestone's original
observer/builder text; then apply the earlier V5-to-V1/V2/V3/V4 patches if needed.

These builders require the frozen prerequisites from the previous milestones;
they are not a clean-checkout binary downloader. Obtain proprietary components
using the publisher's tools and terms as described in [dependencies](DEPENDENCIES.md).
Keep every output directory new, retain failed results, and use the original
shared reservation root. Never overlap native cohorts or retry a nonterminal run.

From the laboratory `bridge/` directory:

```sh
python3 tools/native_video_factory.py build \
  --owned-build results/video-owned-service-build-20261018-04 \
  --out results/factory-build-new
python3 tools/native_video_factory.py run --build results/factory-build-new \
  --mode inspect --out results/factory-inspect-new --reservation-root .
python3 tools/native_video_factory.py run --build results/factory-build-new \
  --mode cpu --route owned --out results/factory-cpu-new --reservation-root .
python3 tools/native_video_factory.py run --build results/factory-build-new \
  --mode hardware --route owned --override present-key --policy observe \
  --out results/factory-observe-new --reservation-root .
python3 tools/native_video_factory.py run --build results/factory-build-new \
  --mode hardware --route owned --override present-key --policy wrong-board \
  --out results/factory-wrong-board-new --reservation-root .
```

Inspect the terminal receipts and the actual policy records before running the
current-board variant. It is valid only for the qualified image/board profile:

```sh
python3 tools/native_video_factory.py run --build results/factory-build-new \
  --mode hardware --route owned --override present-key --policy current-board \
  --out results/factory-current-board-new --reservation-root .
```

`patches/video-factory-v5-to-v{1,2,3,4}.patch` reconstructs the earlier original
observer/main/builder text. The parent-runner patch reconstructs its pre-policy
version. Thirteen text comparisons against frozen sources pass. These are
patches to original project sources, not proprietary shader or driver bodies.
The historical auditor expects the exact dated cohort names in its source:

```sh
python3 tools/audit_video_factory.py --lab-root . --out results/factory-audit-new.json
```

The next driver task is to qualify the native start-method return and its actual
resource/client creation calls. Preserve software and negative policy controls
while doing so; no installed framework replacement is needed for that observation.
