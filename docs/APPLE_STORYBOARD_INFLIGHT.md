# Apple sample storyboard: queued frame-state updates

This builds on the [bounded Apple storyboard/controller experiment](APPLE_STORYBOARD_ICB.md).
The local renderer adaptation no longer waits after every command-buffer commit.
It preserves the sample's original three-frame semaphore and cyclic CPU frame
buffers, the same private GPU frame buffer and its per-frame blit. The host
submits eight controlled frames, alternating two aspect values, then explicitly
waits only for the last command buffer and confirms completion of all eight
before reading captures. It uses one queue. The adapter or the sample's original
semaphore may itself wait; this is not a proof of a completely wait-free path.

The [auditor](apple-storyboard-inflight-validation.json) verifies two direct,
two adapted and two blank processes: 48 frames, 147,456 pixels, 24,576 guard
bytes and 240 adapted draw packets. Direct and adapted images match for both
aspect values; the two values produce different images and the blank frames
remain uniform. Sixteen invalid depth-store actions are refused before the
respective user command buffer is committed. The original storyboard, modified
controller and renderer, and pinned assets are validated as in the preceding
experiment; the actual original executable does not run.

The host records status snapshots immediately after each commit. All 48 current
buffers were reported `Committed`; later snapshots can change. The two adapted
processes observed one pending user command buffer at each snapshot. Some direct
or blank snapshots recorded two pending buffers while iterating statuses, but
this is not an atomic snapshot. In particular, this experiment does **not**
prove two adapted command buffers were simultaneously in flight, GPU parallelism,
a CPU saving or a performance gain. The CPU semaphore may block once three
frames are outstanding. A controlled, non-deadlocking overlap witness remains
necessary for that claim.

The sample's Mac-family assertion is bypassed only inside the adapted local
controller; the reported family is not changed. The test captures its own
render target, not the display. It does not establish visible presentation,
transparent system integration or general ICB behavior. All 83 pinned system
file hashes remained unchanged. Two initial uninstrumented eight-frame trials
are preserved locally and excluded from this six-process cohort.

## Reproduce

Prepare the exact Apple archive, local source and metallib using
[APPLE_CPU_ICB_GAP.md](APPLE_CPU_ICB_GAP.md). Build and run on the qualified
x86_64 macOS environment, with a graphical session. The test briefly displays
an instrumented sample window. Use fresh directories and serialize GPU work.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
LEGACY='/path/to/render_state_carrier.metallib'
python3 tools/build_from_source.py --out build/apple-inflight-new
A="$PWD/build/apple-inflight-new"
E=bridge/experiments/apple_storyboard_inflight
B="$LAB/results/apple-inflight-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$A" --sample "$S" --legacy "$LEGACY" --vertex "$S/apple.metallib" --manifest "$E/profiles.json" --out "$B"
for n in 1 2; do
  for mode in direct auto blank; do
    python3 "$E/experiment.py" run --lab "$LAB" --build "$B" --mode "$mode" --out "$LAB/results/apple-inflight-$mode-$n-new"
  done
done
python3 "$E/audit.py" --sample "$S" --build "$B" --archive "$A" --runs "$LAB/results/apple-inflight-direct-1-new" "$LAB/results/apple-inflight-auto-1-new" "$LAB/results/apple-inflight-direct-2-new" "$LAB/results/apple-inflight-auto-2-new" "$LAB/results/apple-inflight-blank-1-new" "$LAB/results/apple-inflight-blank-2-new" --out "$LAB/results/apple-inflight-audit-new.json"
```
