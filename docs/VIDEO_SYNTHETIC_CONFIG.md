# Synthetic video-provider configuration boundary

This experiment extends an existing **own-process synthetic** test of the separately acquired 10.12.6 NVIDIA video provider. The objects, connection, data buffer and scalar `0x105` response are fabricated; the fence call also returns fabricated success with zeroed outputs. The host makes no explicit video-selector call; the three guarded IOKit counters remain zero in the final runs. It does not establish a real video fence or decode a frame. This is an ABI investigation, not a functioning video provider.

After the synthetic fence response, the provider naturally reaches `IOAccelDeviceGetConfig`. A locally interposed guard verifies the synthetic device token and returns a refusal without calling the original. In two independent, signed final hosts, that guard was called once, the provider returned 11, the original output slot stayed zero, sentinel guards remained intact, and synthetic device/shared/context resources were released. The added guard is calibrated before the call and its import slot and the corresponding pinned provider instructions are checked. The earlier 16 slots are checked as well. Three other final processes cover inspection, wrong-image refusal and all-null input refusal. The common cooperative reservation reports all five processes terminal and nonoverlapping. [Cohort audit](video-synthetic-config-validation.json).

## Preserved failed attempt

The first exploratory build fabricated fence success without guarding `IOAccelDeviceGetConfig`. Its signed process exited with SIGSEGV: the crash report shows the fake device token reaching `IOAccelDeviceGetConfig`, followed by `objc_msgSend` on an invalid address. It terminated and released its cooperative reservation. The crash occurred before the normal counter report, so it cannot establish the absence of other driver or system activity. The added, pinned guard prevented that observed failure in the subsequent runs. [Sanitized crash evidence](video-synthetic-crash-validation.json).

The test process may execute historical provider and system initializers. The three raw IOKit guards and checked import slots are not exhaustive instrumentation of every system call. The experiment exits with `_exit` without qualifying provider destructors or normal lifecycle. Fabricating success and denying configuration cannot establish the real configuration contract, kernel compatibility, safe decode submission or video performance.

## Sources and re-audit

[The stage guard](../bridge/experiments/sierra_fence/stage-guard.mm) and [coordinator](../bridge/experiments/sierra_fence/coordinator.py) are published. The guard's leading comment was corrected after the test; the auditor checks that this is its only difference from the tested source. The original local host and its pinned instruction bytes remain in the private lab rather than being published. Consequently, this is not a standalone clean-checkout build.

The auditor rechecks the frozen local builds, signed process manifests, retained outputs and static evidence. It does not rerun the provider:

```sh
python3 bridge/experiments/sierra_fence/audit.py \
  --lab "$LAB" --out "$LAB/results/video-synthetic-config-audit-new.json"
```

The next dependency is to determine the actual device-configuration contract and live dispatch without passing synthetic objects to unguarded framework functions. Any future integration still needs correct ownership, cleanup and independent hardware-video results; the [dispatch comparison](VIDEO_PROVIDER_DISPATCH.md) remains static.
