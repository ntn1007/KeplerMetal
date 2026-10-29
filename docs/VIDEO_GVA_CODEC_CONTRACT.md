# `IOGVACodec`: bounded string contract and NVIDIA sources

The pinned AppleGVA path treats a non-null result of its `IOGVACodec` query as
an input to `CFStringGetCString`, using a **32-byte buffer** and encoding
constant `0x600` (`kCFStringEncodingASCII`). It sets the node's `0x463` byte
to 1 before that conversion; the inspected instruction sequence does not check
the conversion result. This is a static observation of one path. The existing
[runtime observation](VIDEO_GVA_PROPERTY_NODE_LINK.md) saw a null value, so the
non-null conversion has not been observed in AppleGVA.

Apple documents that `CFStringGetCString` expects a `CFString`, requires space
for the terminator, and can fail on conversion or insufficient space.
[Apple: CFStringGetCString](https://developer.apple.com/documentation/corefoundation/cfstringgetcstring%28_%3A_%3A_%3A_%3A%29?language=objc).
An original CPU-only control with synthetic strings passed for 31 ASCII bytes
and returned false for 32 ASCII bytes and for a non-ASCII sample, with guard
bytes intact. These examples establish neither a valid NVIDIA string nor
complete acceptance rules. A Boolean used in the earlier VideoToolbox
**presence-only** counterfactual is not an established valid input to this
separate AppleGVA string call.

## What the retained driver artifacts show

| Artifact inspected | Result in the plist |
| --- | --- |
| Apple GeForce 10.3.2 from the retained signed High Sierra update | No `IOGVACodec` key; video bundle is `GeForceVADriver` |
| Installed Apple GeForce 16.0.0 | No `IOGVACodec` key; video bundle is `GeForceVADriver` |
| NVIDIA WebDriver 387.10.10.10.40.140 | No `IOGVACodec` key in any of the ten kext `Info.plist` members examined |

This is a bounded plist search, not a search of every binary or runtime path.
The property could be created dynamically or supplied elsewhere. The
WebDriver's retained package hashes are recorded in the
[audit receipt](video-gva-codec-contract-validation.json); its nested payload
was freshly extracted from that package and hash-checked. The current
`pkgutil` check reports an expired signing certificate, so current package
trust is **not** claimed. No installer was executed. The High Sierra GeForce
bundle passed `codesign --verify --strict`; the origin of its retained Apple
update is described in [the previous comparison](VIDEO_HIGH_SIERRA_COMPARISON.md).

As format controls, installed Intel ICL and AMD Navi plists contain the
strings `Gen11` and `AMDVCN2` respectively. They are **not** NVIDIA values or
evidence that those devices are active here. No legitimate GTX 880M value has
yet been identified. Supplying one of these other-vendor values, an arbitrary
string or a Boolean would be an experiment, not evidence of Kepler support.

No GPU or vendor program was executed for this audit; no driver, system or OCLP
component was changed. The next useful work is to find the actual NVIDIA
producer or a historical runtime record that binds the value to a compatible
GPU and driver, before considering a process-local counterfactual.

## Reproduction on the retained profile

The NVIDIA package was previously obtained from the
[NVIDIA download location](https://us.download.nvidia.com/Mac/Quadro_Certified/387.10.10.10.40.140/WebDriver-387.10.10.10.40.140.pkg).
The package, High Sierra bundle and AppleGVA captures are private inputs and
are not included here. The audit extracts one pinned payload into a temporary
directory, reads its ten plists without installing it, builds the original CPU
control and removes temporary files. The destination must not exist.

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
HIGH='/path/to/high-sierra-extract/System/Library/Extensions/GeForce.kext'
python3 bridge/experiments/video_gva_codec_contract/audit.py \
  --package "$R/video-transport-progress-20261016/official/WebDriver-387.10.10.10.40.140.pkg" \
  --high-bundle "$HIGH" \
  --current-plist /System/Library/Extensions/GeForce.kext/Contents/Info.plist \
  --property-region "$R/gva-stack-caller-20261028-01/function-region.private.bin" \
  --property-map "$R/gva-stack-caller-stubs-20261028-01.json" \
  --out "$R/gva-codec-contract-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_codec_contract.py'
```
