# AppleGVA cached codec-byte path: static observation

In the pinned AppleGVA function capture, a list loop clears byte `0x463` on
entries with a nonzero 32-bit field at `0x450`. A later search compares that
field against an input value. On a match, it compares the entry's byte `0x461`
with another input byte and checks that the entry's byte `0x08` is nonzero.
Only if both comparisons pass does this path write `1` to `0x463`, then jump
past the new-entry/property-query sequence for that iteration. A mismatch
branches elsewhere and does not perform that write in the inspected path.

The separate new-entry path calls the mapped `IORegistryEntryCreateCFProperty`
for `IOGVACodec`. When its return is non-null, it sets `0x463` and passes
`entry + 0x08` as the destination of the mapped `CFStringGetCString` call.
Thus the checked cached byte is at the same *structure-relative offset* as
that conversion destination. The code sets the flag before conversion, and
the inspected sequence does not check the conversion return. A non-null
property alone therefore does not establish a nonempty valid cached string.

These are **static facts for a pinned code capture**, not an observation that
an entry was reactivated during a video request. The two paths need not have
operated on the same allocation or the same invocation; the entry lifetime,
all writes to the buffer, inputs, branch reachability, and conversion success
remain unproved. The numerical `0x450` field and input match are not proof of
registry object identity. No legitimate NVIDIA value, hardware decoding,
fix or general rule for other OS versions has been established.

This adds a testable distinction to the [earlier property-to-node correlation](VIDEO_GVA_PROPERTY_NODE_LINK.md):
a future controlled observation must distinguish a **new property query** from
a **matching cached entry** and observe its first byte, its lifecycle, and the
relevant branch. Replacing a missing property with an arbitrary string would
not prove it is an NVIDIA value or that the resulting provider is valid.

The private 2,669-byte capture has SHA-256
`f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19`;
the audit verifies four instruction-window hashes, nine relative branch
targets and the separately pinned call map. The mapping is static, not proof
of runtime call targets. [Sanitized results](video-gva-cached-codec-validation.json)
contain no Apple binary. The synthetic CPU tests exercise the audit, not the
AppleGVA code. No GPU or vendor program was executed, and no system or OCLP
component changed for this analysis.

## Reproduction

```bash
R='/path/to/nvidia-880m-lab/bridge/results'
python3 bridge/experiments/video_gva_cached_codec/audit.py \
  --region "$R/gva-stack-caller-20261028-01/function-region.private.bin" \
  --mapping "$R/gva-stack-caller-stubs-20261028-01.json" \
  --out "$R/cached-codec-audit-new.json"
python3 -m unittest discover -s tests -p 'test_video_gva_cached_codec.py'
```

The auditor refuses different inputs and an existing output path. Function
boundaries come from the retained capture's `LC_FUNCTION_STARTS` metadata;
source-level function identity was not proved. Full details of the property
call and earlier observations remain in [the codec contract](VIDEO_GVA_CODEC_CONTRACT.md).
