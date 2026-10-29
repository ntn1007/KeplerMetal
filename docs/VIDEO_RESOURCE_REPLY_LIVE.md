# Ordinary Metal resource reply and live wrapper

Two signed iMac processes each create an ordinary public 4 MiB shared Metal buffer after a small warmup allocation. In each, a process-local observer forwards the **existing Metal/IOAccelerator call unchanged** and records two selected 64-bit reply fields temporarily in memory. While the new buffer is still alive, the host reads two fields of its pinned IOAccelerator resource wrapper and compares them with the captured pair. Both comparisons match; a deliberately changed comparison value does not. No raw address is exported in the result.

This connects a runtime observation to the preceding [static reply analysis](VIDEO_REPLY_IDENTITY.md) for an **ordinary Metal resource**. It does not prove that a Metal buffer is a video buffer, that any video reply exists, or that the buffer can be submitted to a video context. No explicit GPU dispatch, video selector, hardware decode or speedup is established. The CPU checks the 4 MiB pattern; it is not a GPU computation.

## Scope and evidence

The observer captures only a successful selector-0 `IOConnectCallMethod` completion during the target-allocation phase, from the pinned `IOAccelResourceCreate` return offset `0x2072`, with zero scalar inputs, 168-byte input and a reported 89-byte output. It verifies that the original output capacity is at least 89 bytes, then copies only offsets `0x10` and `0x18`. The host pins the implementation and the `MetalOld` resource accessor code and Objective-C metadata before reading the resource pointer and two fields at resource offset `0x48`. It does not call the accessor. The code does not alter the original call's arguments, output, return code or saved errno.

The six serial processes comprise one inventory, one hook calibration, two no-target baselines and two target allocations. Each target is CPU-checked in full and its weak Metal reference clears after the scoped release; that does not establish destruction of the underlying kernel resource. Baselines record no matching target-creation event. The audit checks the signed executables, frozen host/runner, selected driver-profile observations before and after each host, metadata, event count, results and terminal nonoverlapping cooperative reservations. It cannot independently recalculate the comparison from raw pointers because they are not exported; the match and wrong-value control are evaluated inside the test process. The calibration validates the interposer on null-port calls, while the captured native call independently confirms observation at the selected caller. Coverage does not extend to all dyld bindings, threads or unrelated work. The selected driver profile checks are recorded by the runner; its imported support modules were not individually frozen per run.

[Audit](video-resource-reply-live-validation.json) · [six offline audit mutations](video-resource-reply-live-mutations.json). The mutations alter copied receipts, not the original evidence; one earlier mutation-harness attempt failed because it attempted exclusive creation over a copied file and is retained in the private lab. An earlier exploratory inventory/control/target build passed but is not included in the final cohort. No system component, driver, OCLP or firmware was modified.

## Reproduction

Use the exact pinned iMac profile, a cooperative GPU reservation root, and fresh paths. Inventory identifies the current registry ID; obtain it from the resulting `verification.json` rather than reusing a previous boot's ID. Do not retry a process whose termination is unknown; the runner does not kill it on timeout.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
E=bridge/experiments/video_resource_reply_live
B="$LAB/results/reply-live-build-new"
python3 "$E/experiment.py" build --out "$B"
python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --mode inventory --out "$LAB/results/reply-live-inventory-new"
RID='<registry_id from inventory verification>'
python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --mode control --registry-id "$RID" --out "$LAB/results/reply-live-control-new"
for n in 1 2; do
  for mode in baseline large; do
    python3 "$E/experiment.py" run --build "$B" --lab "$LAB" --mode "$mode" --registry-id "$RID" --out "$LAB/results/reply-live-$mode-$n-new" || exit 1
  done
done
RUNS=("$LAB/results/reply-live-inventory-new" "$LAB/results/reply-live-control-new" \
 "$LAB/results/reply-live-baseline-1-new" "$LAB/results/reply-live-large-1-new" \
 "$LAB/results/reply-live-baseline-2-new" "$LAB/results/reply-live-large-2-new")
python3 "$E/audit.py" --build "$B" --runs "${RUNS[@]}" --out "$LAB/results/reply-live-audit-new.json"
python3 "$E/mutations.py" --build "$B" --runs "${RUNS[@]}" --out "$LAB/results/reply-live-mutations-new"
```

The next experiment must establish the legitimate video-buffer producer, its actual reply and ownership contract independently. Matching ordinary resource fields is not permission to fabricate or forward a video request.
