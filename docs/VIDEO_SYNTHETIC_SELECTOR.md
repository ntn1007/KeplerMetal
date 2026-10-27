# Synthetic provider path through device configuration

The preceding [guarded experiment](VIDEO_SYNTHETIC_CONFIG.md) stopped at `IOAccelDeviceGetConfig`. This follow-up uses an isolated signed process with fabricated device, shared/context objects, data buffer, `0x105` response and fence success. The configuration guard now also fabricates success and writes zero to each of five output words. These values do **not** establish the real device configuration ABI or the values needed by GK104.

With that counterfactual, the old provider naturally attempts scalar selector `0x103`. The locally interposed scalar guard accepts only the expected synthetic connection, zero input count and one output slot; it writes a zero to the output and refuses the call without forwarding it. The provider returns 11. The independently pinned historical table labels `0x103` as `get_fb_config`, but this does not prove the installed driver's live dispatch or compatibility. The historical machine-code range and retained analysis record for the caller are checked separately.

Two signed, terminal and nonoverlapping test processes reach the same refused request. A further three inspect or exercise wrong-image and null-argument controls. In both synthetic runs, allocation and release counters, sentinel guards, restored globals and all checked import slots pass. Three guarded raw IOKit counters remain zero; that is not exhaustive monitoring of all system operations or provider initializers. No real video selector, fence, framebuffer configuration or decoded hardware image is established. [Machine-readable audit](video-synthetic-selector-validation.json).

The test returns through the provider's failure path; the process uses `_exit` and does not qualify normal provider destructors or service lifetime. Success values, class identities, data mappings and actual kernel transport must be qualified before integration. This step does not repair or replace any installed driver or establish a performance gain.

## Sources and re-audit

[The synthetic stage guard](../bridge/experiments/sierra_config/stage-guard.mm), [coordinator](../bridge/experiments/sierra_config/coordinator.py) and auditor are published. The guard's first comment was corrected after the build; the auditor verifies that this is its sole difference from the exact tested source. The original local host with pinned proprietary instruction bytes and the provider binary remain private, so this is not a standalone clean-checkout build.

The following command rechecks the existing lab builds and receipts; it does not rerun a provider or send commands:

```sh
python3 bridge/experiments/sierra_config/audit.py \
  --lab "$LAB" --out "$LAB/results/video-synthetic-selector-audit-new.json"
```
