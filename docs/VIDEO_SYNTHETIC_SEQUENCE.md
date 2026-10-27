# Synthetic video-provider initialization sequence

The earlier [Metal device observation](METAL_DEVICE_OBJECT.md) recorded five configuration words `768, 0, 0, 0, 1` on the qualified GTX. This experiment supplies those words to a **synthetic** device-configuration guard in a separate test of the historical 10.12.6 NVIDIA video provider. The real Metal device object is not passed to the provider.

After fabricated `0x105` and fence responses, the provider requests `0x103`, `0x104`, `0x102` and `0x100`, in that order. The guard returns fabricated zero values and success for the first three, then writes zero and refuses `0x100` locally. It validates the synthetic connection, ordering, zero inputs and one output slot; an out-of-order calibration is refused. None of these video selectors is forwarded by that guard. The configuration words come from a real device observation; the other fabricated responses are not validated for the hardware.

Two signed, terminal nonoverlapping processes reproduce the sequence and failure return 11, with the checked guards, sentinels, simulated-object releases and global-state restoration intact. Inspection, wrong-image and null-argument controls are separate. Static evidence pins the relevant historical call sites; the real configuration audit is hash-bound as the source of the five words. The raw IOKit guard counters stay zero in the recorded runs, but provider and framework initializers and every possible system path are not exhaustively traced. [Machine-readable audit](video-synthetic-sequence-validation.json).

The experiment uses zeroed synthetic allocation and terminates with `_exit`; it does not qualify provider destructor behavior, actual framebuffer/configuration values, driver dispatch, resource ownership or decoding. There is no hardware-video execution or performance claim. Before integration, the actual live dispatch and all required outputs must be established without issuing unqualified commands.

## Sources and re-audit

[The stage guard](../bridge/experiments/sierra_sequence/stage-guard.mm), [coordinator](../bridge/experiments/sierra_sequence/coordinator.py) and auditor are published. The guard's leading comment was corrected after testing; the auditor verifies that it is the only source difference. The local host and pinned proprietary code bytes remain in the private laboratory, so this is not a standalone build.

Recheck existing frozen artifacts without rerunning the provider:

```sh
python3 bridge/experiments/sierra_sequence/audit.py \
  --lab "$LAB" --out "$LAB/results/video-synthetic-sequence-audit-new.json"
```
