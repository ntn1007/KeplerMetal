# Video-provider and kernel dispatch comparison

A separately acquired macOS 10.12.6 NVIDIA video provider is a potential source of information about a real implementation, but its compatibility with the current GTX stack is unproved. This offline comparison establishes a concrete interface difference before attempting any provider integration.

The pinned 10.12.6 GeForce kernel image has an `nvVideoContext` override and a 13-entry historical method table for selectors `0x100`–`0x10c`. The historical provider code includes calls to seven of those selectors; its creation path requests `0x105` with one scalar input and capacity for two scalar outputs. In the historical kernel symbol table, the matching method is named `acquire_channel`.

For the pinned current GeForce image, the examined vtable relocation instead names `IOAccelContext2::getTargetAndMethodForIndex`; the examined current base lookup handles indices through 7 before its fallback. This is a **static difference** in file contents and relocations. It does not establish the actual live vtable, prove that every request follows that fallback, or prove that selector `0x105` would fail. The metadata interpretation also uses a modern published XNU header, not a verified 10.12 kernel ABI. Do not issue a private selector on the strength of this report.

The comparison checks exact file hashes, method-table bytes, symbols, relocations, selected disassembled instructions, and eleven frozen REA records with subject identities. Two negative controls reject a modified table and a missing symbol. [Machine-readable results](video-dispatch-validation.json).

This is separate from the [legacy AppleGVA experiment](VIDEO_LEGACY_BACKEND.md): that experiment observed a stub in the installed provider; this comparison examines a different, separately acquired provider and historical kernel. No native provider was loaded by this audit, no selector was called, and no hardware video was decoded. A usable bridge would still require live dispatch identification, matching ABI and resource ownership, safe command transport, teardown and independent pixel validation.

A [High Sierra follow-up](VIDEO_HIGH_SIERRA_COMPARISON.md) identifies a matching return-14 provider stub and inherited lookup in that separately signed update; its static lookup also returns null above 7. Runtime dispatch remains unproved.

## Reproduction

Use the existing private lab tree, including its pinned historical binaries, retained REA records and public XNU header. No vendor binary is distributed by this repository. The audit rejects any changed input and creates a fresh report:

```sh
python3 bridge/experiments/video_dispatch/audit.py \
  --lab "$LAB" --out "$LAB/results/video-dispatch-audit-new.json"
```

The audit reads installed driver files but does not modify them. Reproduction requires the exact historical and current profiles listed in the output and the pinned `compare_video_profile.py`. A missing or updated file requires a new qualification; it must not be silently re-pinned. See [dependencies](DEPENDENCIES.md) for obtaining vendor components.
