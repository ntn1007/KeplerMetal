# AppleGVA board read on the current profile

Three new hardware-required H.264 test processes observed the pinned AppleGVA board reader obtain a CFData value containing this iMac's `board-id`. The value is `Mac-F2268DAE`, matching a separate read-only `ioreg` observation. In all three, decoder creation still returned **-12913 with zero hardware images**. This proves a particular public data-read call occurred in the process-local experiment; it does not establish which candidate was selected or why hardware decoding failed.

The observer matches the original caller return at AppleGVA image offset 152101, UUID `ca5414f369373c059ea2d82b35afd4f0` and SHA-256 pins for the 213-byte reader and 1,136-byte selection region. It forwards the public `CFDataGetBytePtr` result and preserves the observed `errno`; it reads at most 63 bytes from a readable returned CFData buffer. A public backtrace did **not** show the exact expected selection-region return in the three records. An absent frame can reflect unwinding or control flow, so neither reachability nor nonreachability of that particular branch is established. The observer changes the calling stack and timing; a small direct CFData calibration checks its basic interposition and returned content, not every ABI or application.

## Process-local profile update and controls

The historical dependency observer required accelerator registry ID 4294968458. The currently observed sole `nvAccelerator` has ID 4294968416; these IDs are instance identifiers and may change after a restart. For this experiment only, the builder creates a new dependency library from the original text with exactly the ID and its adjacent negative-control ID changed. It verifies the current accelerator identity, the current GeForce file hash, historical inputs and the unchanged remaining source and profile. It relinks a **copy of our own test application** to that library. No vendor binary, original laboratory executable, system component or OCLP setting is altered. This is an explicitly scoped counterfactual experiment, not a driver update.

All hardware runs require hardware decoding and use the previously described [owned native transport and dependency experiment](VIDEO_FACTORY_POLICY.md). The current-board cases also use the previously qualified process-local policy copy. Three runs with the observer and three without it all report -12913, zero hardware images, one successful dependency substitution and one pixel-buffer-pool call. The pool call is not a decoded image or proof of video-engine execution. One original-policy and one wrong-board control report -12906 with zero images. A software control decodes six images whose **691,200 bytes** match the independent CPU reference. The 11 processes include calibration and inspection; their signed binaries, terminal reservations, source/profile identities, choices and nonoverlapping intervals are rechecked by the [audit](video-gva-board-observation-validation.json). Four altered evidence cases are refused by the [offline mutation test](video-gva-board-observation-mutation.json).

An earlier exploratory observer rejected the lowercase letters in `Mac-` when formatting this value and sometimes did not observe the pool witness. Those receipts remain in the local lab and are excluded from the final cohort. The fixed observer and plain controls shown above are distinct fresh processes. Neither set measures performance or proves complete native service lifetime.

Next, qualify an observer for the actual selection and its output without relying on an absent backtrace frame. Inspect the selected candidate's provenance and failure boundary before attempting an implementation. Arbitrary private calls, fabricated selector requests and system deployment remain outside this experiment.

## Reproduction on the exact profile

The builder requires the existing pinned private laboratory host and dependencies. Obtain vendor components locally as described in [DEPENDENCIES.md](DEPENDENCIES.md); they are not included here. Verify the current accelerator ID, driver and board identity before choosing values. The builder refuses a changed profile. All outputs must be fresh and all runs share the same lab reservation root.

```sh
EXP=bridge/experiments/video_gva_board_observer
python3 "$EXP/experiment.py" build --base "$LAB/results/video-factory-resolver-build-20261018-09" --out "$LAB/results/gva-board-build-new" --accel-id 4294968416
for mode in calibration inspect cpu native wrong; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-board-build-new" --out "$LAB/results/gva-board-$mode-new" --reservation-root "$LAB" --mode "$mode"
done
for n in 1 2 3; do
  python3 "$EXP/experiment.py" run --build "$LAB/results/gva-board-build-new" --out "$LAB/results/gva-board-current-$n-new" --reservation-root "$LAB" --mode current
  python3 "$EXP/plain.py" --build "$LAB/results/gva-board-build-new" --out "$LAB/results/gva-board-plain-$n-new" --reservation-root "$LAB" --policy current-board
done
HOSTS=("$LAB/results/gva-board-calibration-new" "$LAB/results/gva-board-inspect-new" "$LAB/results/gva-board-cpu-new" "$LAB/results/gva-board-native-new" "$LAB/results/gva-board-wrong-new" "$LAB/results/gva-board-current-1-new" "$LAB/results/gva-board-plain-1-new" "$LAB/results/gva-board-current-2-new" "$LAB/results/gva-board-plain-2-new" "$LAB/results/gva-board-current-3-new" "$LAB/results/gva-board-plain-3-new")
python3 "$EXP/audit.py" --build "$LAB/results/gva-board-build-new" --out "$LAB/results/gva-board-audit-new.json" --hosts "${HOSTS[@]}"
python3 "$EXP/mutate.py" --build "$LAB/results/gva-board-build-new" --hosts "${HOSTS[@]}"
```

This exact cohort and audit are deliberately restricted to the observed ID and driver profile; a different boot's ID requires a new independently checked build and qualification, not a silent reuse of these results.
