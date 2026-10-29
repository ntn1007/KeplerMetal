# Historical NVIDIA classification and the current AppleGVA filter

A retained AppleGVA 10.13.6 x86_64 image has two relevant static paths for the
value `0x01040008`:

- A diagnostic path maps that numeric value to the string `NVIDIA, VP4`.
- In an enumeration path, after the relevant node flag checks, a comparison
  against that value leads to incrementing a candidate counter and saving the
  node pointer in a register. This does not by itself prove that the candidate
  is subsequently selected or can decode video.

In the [current observed path](VIDEO_GVA_CLASSIFICATION_WITNESS.md), the
numeric field of the node seen in two synthetic-property requests was also
`0x01040008`. The current classifier has a different finite set of accepted
values; the instrumented process reached classification and then the skip
instruction, with the same observed pointer value. The current field was at
node offset `0x428`; the old comparison read a field at `0x408`. The structural
layout and implementation are therefore not interchangeable on that basis.

This comparison ties the earlier historical observation to the newer runtime
witness. It gives a concrete reason to investigate a **version-dependent video
selection path**, not permission to substitute an Intel/AMD identifier or to
install the old framework. The old image is not executed here. Its label does
not prove which physical engine the current request used, that old downstream
interfaces match Tahoe, or that the GTX can decode through this path today.
VideoToolbox still returns `-12913` and zero hardware frames in the tested
current configuration.

## Provenance and limits

The historical file is the x86_64 slice of the previously retained
`Universal-Binaries/10.13.6` image from Dortania `PatcherSupportPkg` commit
`3250ca07ca49e3f8c743066381b5688028681de8`, recorded by the original laboratory
report. The audit checks that the universal file contains the exact slice,
checks its UUID and hashes, and checks five instruction windows and the label.
It also binds two previously retained REA/Ghidra 12.1.4 records:
`ev_247b9e60588040bc9a1d23ca7dc8ff8f96c7143b01a604d49f9704992436a124` and
`ev_931bf92d58c7106a382a89793c44f1a449547dd15df2b697589287a5b3134103`.
A fresh REA query also placed the comparison at `0x24163` inside the function
starting at `0x23e22` (evidence `ev_81dca80682a4c08f220c373d693226e25e634cd288d8f1fda770fcbf2af45274`).
The standalone thin file does not pass `codesign --verify --strict` outside its
original bundle, so this comparison does **not** claim current signature trust
or independently establish the upstream commit. No Apple binary is published.

The [sanitized receipt](video-gva-historical-classification-validation.json)
links that static evidence to the current witness audit and private region.
There is no new execution of a vendor program or the GPU in this comparison.

## Reproduction

Requires the previously retained, private historical image, REA evidence and
current witness audit. The audit refuses different hashes or an existing output.

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
python3 bridge/experiments/video_gva_historical_classification/audit.py \
 --universal "$R/video-transport-progress-20261016/references/Universal-Binaries/10.13.6/System/Library/PrivateFrameworks/AppleGVA.framework/Versions/A/AppleGVA" \
 --legacy "$R/video-enumeration-progress-20261018/AppleGVA-10.13.6-x86_64.private.macho" \
 --rea "$R/video-enumeration-progress-20261018/REA-legacy-gva.private.json" \
 --current-region "$R/video-gva-session-enumeration-inner-20261018/function-region.private.bin" \
 --current-audit "$R/gva-class-witness-audit-20261029-01.json" \
 --out "$R/historical-classification-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_historical_classification.py'
```
