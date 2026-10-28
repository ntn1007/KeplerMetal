# Archived legacy AppleGVA provider arguments

The preceding [registration study](VIDEO_PROVIDER_REGISTRATION.md) asked where the historical provider's input values came from. A broader search of the existing private lab found that this question had already been partly investigated on 2026-10-27. This report re-audits those existing records; **no GPU test or provider execution was repeated**.

In the archived AppleGVA 10.13.6 static evidence, enumeration calls `CGSAcceleratorForDisplayAlias` and writes returned values into an indexed array. The legacy factory prepares a pointer to that array, a mask and a selected index, then passes the structure to the selected provider's create entry. These are static observations of the pinned old AppleGVA image, SHA-256 `54dc80c41bab45492d1eb601fb1d242b513107645d068bf24edee155b965681f`. They do not establish what an unmodified current AppleGVA process passes or whether all array entries refer to the GTX.

Two archived own-process hardware-required tests explicitly selected this legacy AppleGVA and used earlier scoped policy and dependency counterfactuals. An instrumented `dlsym` lookup replaced the pinned installed NVIDIA stub's create pointer with a test gate that returns the same numeric value, 14. On reaching the pinned callsite, the gate inspected the caller's arguments without invoking the Sierra provider. Both records show:

| Observed field | Value |
| --- | --- |
| Selected index | 0 |
| Mask | `0x0000000f` |
| Required array length calculated from the mask | 4 words |
| Selected entry | Nonzero; exact value was not recorded |
| Region for four words | Readable at observation time |

The gate read the selected word only, not all four. Its memory-region check does not prove allocation bounds, ownership or lifetime. The legacy caller was selected in a controlled process, not the default macOS path. These observations meet the *local necessary conditions* identified in the Sierra provider's static analysis; they do not show that those words are meaningful to it, that the selected object belongs to the current GTX, or that any kernel selector or video work is safe.

The [new independent re-audit](video-provider-fields-reaudit-validation.json) validates the pinned build inputs and observer source, archived REA identities, actual signed-process manifests, four nonoverlapping terminal receipts, gate output and changed-route control. The software control's six archived output images match **2,764,800 bytes** of their pinned reference files. Three hardware-required cases, including the wrong-name control, returned `-12913` and zero images. The results include two active observations, one wrong-name control and one software control; they are historical observations, not four new GPU runs.

The earlier lab also already contained an offline `sierra_video_config_model.py` with essentially the same necessary checks. The public model and tests added in the preceding commit are a separately written, source-available version; they should not be presented as the first discovery of that model. The earlier auditor's results and original model remain unchanged.

## Remaining work

The [follow-up observation](VIDEO_PROVIDER_SERVICE.md) identifies the selected entry as this boot's GTX accelerator on a controlled legacy route. Determine the other entries' provenance and the selected right's lifetime, and establish the mismatch between the historical provider's kernel selector contract and the current live driver without issuing unqualified selectors. The modern default AppleGVA path, actual provider compatibility and GPU video decoding remain unproved. No system driver, framework, OCLP or firmware was modified by this re-audit.

## Reproduction

Use the retained private laboratory artifacts; no vendor code or captured frames are included in the repository. The auditor rejects changed pinned inputs and writes a fresh report.

```sh
python3 bridge/experiments/video_provider_fields_reaudit/audit.py \
  --lab "$LAB" --out "$LAB/results/video-provider-fields-reaudit-new.json"
python3 -m unittest discover -s tests -p 'test_video_provider_*' -v
```
