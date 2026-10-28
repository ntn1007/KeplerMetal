# AppleGVA constructor selector observed in the test process

Three fresh iMac processes recorded **`r14 = 2`** immediately before the
same naturally occurring allocation call in the previously studied AppleGVA
constructor branch. The recorded requested size was **1,536 bytes** in each
process. This narrows the earlier [static candidates 2 and 9](VIDEO_GVA_DISPATCH.md)
to an actual value in these instrumented executions. The meaning of value 2
as a codec, provider or hardware class remains unproved.

The associated constructor's static type metadata is examined separately in
the [RTTI audit](VIDEO_GVA_RTTI.md); its completion at runtime remains unproved.

These are **process-local counterfactual H.264 requests**: they retain the
earlier scoped `IOGVACodec` presence substitution and current-board policy
entry. All require hardware decoding. Each still returns **-12913 and zero
images**. Two comparison processes using the same host without the new register
observer return the same status and zero images. This does not show that the
observer preserves every possible behavior, nor that the video engine executes.

## Observation and controls

The new library interposes the public C++ nothrow allocation function only in
the test process. The x86_64 tail filters on one original return address,
records only the selector register, allocation size and matching caller, and
tail-jumps to the original allocator. It does not dereference allocator
arguments or modify its return value. It does not patch AppleGVA instructions,
call a private function or modify the system registry. Calls outside the one
matched return address are not recorded.

Before arming, the observer requires the specific AppleGVA image UUID and
SHA-256 of its **719-byte live code region**. It also checks the original
allocator address against the loaded `libc++abi` path and pinned image offset.
In each of the three positive processes the image and allocator checks passed,
one event was recorded, and no event was dropped or pending. The earlier static
instruction mapping connects that callsite to the `r14` value; it does not
establish the semantic name of the value.

The [independent cohort audit](video-gva-register-validation.json) covers nine
signed, terminal, nonoverlapping processes:

- Three current-board observations, each recording `2` and returning -12913.
- Two same-host current-board controls without the new observer, also -12913.
- Two wrong-board controls, each -12906 with no matched event while the image
  and allocator checks succeeded. A zero count only covers this hook and
  callsite, not every possible allocation route.
- Two software controls, one with and one without the observer: **12 images /
  1,382,400 NV12 bytes** match the independent CPU reference.

CPU-only calibration checks 256 combinations of selector values and arithmetic
flags against an uninstrumented known-ABI function, including argument and
return forwarding, the stack argument, caller filtering, disabled recording
and saturation. A separate executable and synthetic caller library exercise
dyld interposition against the real public nothrow allocator; the expected
caller records selector 9 and a different caller is excluded. The production
observer uses the same tail, but its AppleGVA activation logic is separate;
the synthetic check is not complete certification of every runtime ABI or
interposition path.

The audit verifies frozen source and executable hashes, signatures, policy
choices, the retained software pixels and reservation receipts. Five
[offline evidence mutations](video-gva-register-mutation.json) are rejected;
the untouched and restored copies pass. Protected files checked by this
experiment retain their pinned hashes. The experiment modifies no installed
driver, framework, OCLP or firmware. It does not establish hardware video,
transparent application integration or a performance gain.

## Reproduction on the qualified profile

The pinned [property-observer build and fixtures](VIDEO_GVA_PROPERTY.md),
shared laboratory reservation and current accelerator registry ID are
required. The builder refuses profile drift. Use new output paths and never
restart while a process or reservation is unresolved. Vendor binaries and raw
captures remain in the private lab.

```bash
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
EXP=bridge/experiments/video_gva_register_witness
BASE="$R/gva-property-build-20261028-01"
BUILD="$R/gva-register-build-new"
CAL="$R/gva-register-calibration-new"
python3 "$EXP/cpu_calibration.py" --out "$CAL"
python3 "$EXP/experiment.py" build --lab "$LAB" --base "$BASE" --out "$BUILD"
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-cpu-on-new" --mode cpu --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-wrong-on-1-new" --mode wrong --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-current-on-1-new" --mode current --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-current-off-1-new" --mode current --witness off
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-current-on-2-new" --mode current --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-wrong-on-2-new" --mode wrong --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-cpu-off-new" --mode cpu --witness off
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-current-on-3-new" --mode current --witness on
python3 "$EXP/experiment.py" run --lab "$LAB" --base "$BASE" --build "$BUILD" --out "$R/gva-current-off-2-new" --mode current --witness off
HOSTS=("$R/gva-cpu-on-new" "$R/gva-wrong-on-1-new" "$R/gva-current-on-1-new" "$R/gva-current-off-1-new" "$R/gva-current-on-2-new" "$R/gva-wrong-on-2-new" "$R/gva-cpu-off-new" "$R/gva-current-on-3-new" "$R/gva-current-off-2-new")
python3 "$EXP/audit.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" --runs "${HOSTS[@]}" --out "$R/gva-register-audit-new.json"
python3 "$EXP/mutate_audit.py" --base "$BASE" --build "$BUILD" --calibration "$CAL" --runs "${HOSTS[@]}" --out "$R/gva-register-mutations-new.json"
```
