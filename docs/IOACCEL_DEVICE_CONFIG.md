# Current IOAccelerator device-configuration boundary

The synthetic legacy-video experiment cannot safely pass a fabricated token to the current `IOAccelDeviceGetConfig`: its first attempt crashed during `IOAccelDeviceGetConfig`, with `objc_msgSend` at the faulting frame. Two subsequent read-only captures and a bounded disassembly of the current x86_64 function clarify why. No selected function was called in these captures.

On the pinned IOAccelerator image UUID `198a776afe0335ee8e537b9f14caabaa`, the first return is at entry offset `0x89`. The inspected instructions check for a null first argument, call an import whose live binding resolves exactly to `CFGetTypeID`, and compare its result with a stored value. On the success path, five 32-bit words are read from offsets `0x270`, `0x274`, `0x278`, `0x280` and `0x288` of the input object and copied to five output pointers. The specific expected type ID, ownership rules, field meanings, actual 880M values and effects of obtaining a valid object remain **unknown**. Do not fabricate an object from these offsets or call the function with incomplete output pointers.

The two independent capture runs record identical entry hashes and resolved-symbol identities. The auditor checks 27 instruction positions through the first return and rejects a deliberately changed entry. It examines the loaded code and binding; it is not a live execution of the function, a GPU test, or a full analysis of the framework. [Machine-readable audit](ioaccel-device-config-validation.json).

This makes the next requirement concrete: identify and qualify how an actual device object is obtained and kept alive, then obtain its configuration through an authorized, correctly typed path. The legacy provider's other synthetic successes and its locally refused `0x103` request remain separate; none demonstrates hardware video decoding.

## Reproduction

Capture bytes remain private in the laboratory; neither the repository nor the audit report contains the proprietary code. These commands load the system framework in fresh processes, which may run its initializers, but do not call the selected entries or submit GPU commands. Use fresh paths and the current qualified host profile:

```sh
python3 bridge/experiments/ioaccel_device/capture.py "$LAB/results/device-capture-new-1"
python3 bridge/experiments/ioaccel_device/capture.py "$LAB/results/device-capture-new-2"
python3 bridge/experiments/ioaccel_device/audit.py \
  --captures "$LAB/results/device-capture-new-1" "$LAB/results/device-capture-new-2" \
  --work "$LAB/results" --out "$LAB/results/device-config-audit-new.json"
```

The capture refuses changed image UUID or configuration-entry hash. The auditor builds a temporary local disassembly container from the captured bytes and removes it after use. A future macOS update requires a new qualification instead of silently changing these pins.
