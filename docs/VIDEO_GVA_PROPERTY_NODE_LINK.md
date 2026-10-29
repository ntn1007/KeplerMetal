# AppleGVA codec property and filtered node: address correlation

In two instrumented H.264 requests, AppleGVA's public
`IORegistryEntryCreateCFProperty` call for `IOGVACodec` returned **null** from
the observed `nvAccelerator` registry entry. A hardware breakpoint immediately
after that call recorded a zero `0x463` byte on the node addressed by the
callee-saved register. Later, in the same thread, the head of the inspected
one-entry list had the **same address** and the same zero byte; enumeration
returned a zero count. Both requests returned **-12913 and zero images**.

Address equality is not a proof that the allocation remained alive throughout
the interval: intervening free and reuse have not been excluded. Nor does the
numeric match between the node's identifier and `IOVARendererID` prove the
identity of that node with the registry object.

The pinned loaded code tests the property result and, if it is null, branches
around one instruction that writes `1` to this node's byte `0x463`. The later
selection code, in the observed flag-zero mode, skips a node whose byte
`0x463` is zero. This provides a concrete conditional explanation for the
observed exclusion. **Neither branch was individually traced**; the code and
register observations do not exclude every other write or cause. An available
property would not by itself prove that a decoder or GPU video engine works.

The earlier process-local substitution concerns VideoToolbox's
`IORegistryEntrySearchCFProperty` dependency check. It does not establish that
AppleGVA's separate `IORegistryEntryCreateCFProperty` query returned a value.
Both requests retained the local dependency and board-policy counterfactuals;
the debugger may affect timing. A wrong-board control, a current-board control
without the marker, and six software frames matching 691,200 CPU-reference
bytes are retained.

Seven CPU-only synthetic processes validate the hardware witnesses, present
and absent property results, matching and different node addresses, bounded
list traversal including a cycle, and an unreadable output address. The marker
checks the AppleGVA UUID and six live region hashes; LLDB independently checks
the six loaded regions. No target instruction is patched. The
[sanitized audit](video-gva-property-link-validation.json) binds the run and
runner hashes, signatures, CPU controls, static null branch and property-call
mapping. Raw addresses, vendor binaries and captures remain in the private lab.
No driver, OCLP, firmware or system file was modified.

## Reproduction

Requires the qualified private lab, static captures, stub mapping and shared
GPU reservation. Use fresh paths; if a debugger or child remains unresolved,
retain the reservation and inspect the existing process rather than restarting.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
EXP=bridge/experiments/video_gva_property_link_witness
BASE="$R/gva-property-build-20261028-01"
CAL="$R/link-calibration-new"
CONTROL="$R/link-reserved-cpu-new"
BUILD="$R/link-build-new"
python3 "$EXP/cpu_calibration.py" --out "$CAL"
python3 "$EXP/reserved_cpu.py" --lab "$LAB" --calibration "$CAL" --out "$CONTROL"
python3 "$EXP/build_gva.py" --lab "$LAB" --base "$BASE" --calibration "$CAL" --reserved-control "$CONTROL" --out "$BUILD"
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/link-cpu-new" --mode cpu --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/link-current-1-new" --mode current --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/link-wrong-new" --mode wrong --witness on
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/link-off-new" --mode current --witness off
python3 "$EXP/run_gva.py" --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/link-current-2-new" --mode current --witness on
python3 "$EXP/audit_gva.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" --reserved-control "$CONTROL" \
  --dispatch-region "$R/video-gva-provider-session-20261018/function-region.private.bin" \
  --enumerator-region "$R/gva-post-constructor-20261029-01/function-region.private.bin" \
  --inner-region "$R/video-gva-session-enumeration-inner-20261018/function-region.private.bin" \
  --property-region "$R/gva-stack-caller-20261028-01/function-region.private.bin" \
  --property-map "$R/gva-stack-caller-stubs-20261028-01.json" \
  --runs "$R/link-cpu-new" "$R/link-current-1-new" "$R/link-wrong-new" "$R/link-off-new" "$R/link-current-2-new" \
  --out "$R/link-audit-new.json"
```
