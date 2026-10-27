# Repeated and concurrent default-device discovery

The opt-in standalone bootstrap now serializes initialization of the scoped
Metal device. Calls to `MTLCreateSystemDefaultDevice` from multiple threads wait
for the first initialization and receive the same scoped device object after
success. A per-thread recursion guard refuses reentrant discovery. If initial
identity, scope creation or factory setup fails, initialization remains
fail-closed for that process rather than retrying or silently returning a native
device. This change is local to the explicitly launched child process.

The bootstrap still accepts only an exact signed client hash, one certified
shader-library snapshot, one GTX 880M, one queue and the previously qualified
render pipeline. It is not a general Metal loader or a system-driver change.
Concurrent queue creation, scope restoration while calls are active, multiple
queues and arbitrary applications or shaders are not qualified. A signed or
hardened third-party application may reject the explicit loading mechanism;
this experiment neither modifies that application nor changes its protections.

## Evidence

A separate public-Metal client, linked without KeplerMetal symbols, starts eight
threads that simultaneously request the default device. It checks object identity
across all eight, requests it once more after joining the threads, then renders
using a CPU-encoded project ICB. The three adapted runs each return one device,
perform one bootstrap initialization, and produce the same 64×48 RGBA32Float
image as the native direct-draw control. A single-call client from the earlier
experiment also reproduces that image. The independent image oracle checks
12,288 channels and both guards per successful render.

Separate controls verify the native ICB failure without injection, refusal of a
wrong shader library, and refusal of a modified signed client. The refused
client exits after its eight concurrent requests; it does not make the ninth
request. All eight final hosts terminate and their intervals do not overlap.
The earlier first cohort is retained locally: its verifier reported nine calls
for the refused client despite the eighth-call exit. The final cohort uses a
corrected verifier; the bootstrap and observed results did not need changing.
[Audit and fingerprints](standalone-multicall-validation.json).

This is a more realistic initialization contract for a process-local adapter,
not proof that an independent third-party application works. It does not add
native Metal 3/4 support, repair the NVIDIA driver or measure a performance gain.

## Reproduction

Use the verified GTX profile, full Xcode/Metal toolchain, a fresh output path,
and the existing shared GPU reservation root `LAB`. The source-only builder
reconstructs the local shader library and signs its own test executables; it
does not distribute Apple or NVIDIA binaries. Execute every host serially.

```sh
python3 tools/build_from_source.py --out build/standalone-multicall
ARCHIVE="$PWD/build/standalone-multicall"
python3 bridge/experiments/standalone_icb/multicall_experiment.py build \
  --library "$ARCHIVE" --out "$LAB/results/multicall-build-new"
for mode in direct auto auto-native wrong-library wrong-client; do
  python3 bridge/experiments/standalone_icb/multicall_experiment.py run \
    --build "$LAB/results/multicall-build-new" --out "$LAB/results/multicall-$mode-new" \
    --reservation-root "$LAB" --mode "$mode" || break
done
for n in 2 3; do
  python3 bridge/experiments/standalone_icb/multicall_experiment.py run \
    --build "$LAB/results/multicall-build-new" --out "$LAB/results/multicall-auto-$n-new" \
    --reservation-root "$LAB" --mode auto || break
done
python3 bridge/experiments/standalone_icb/experiment.py build \
  --library "$ARCHIVE" --out "$LAB/results/multicall-original-build-new"
python3 bridge/experiments/standalone_icb/experiment.py run \
  --build "$LAB/results/multicall-original-build-new" --out "$LAB/results/multicall-original-new" \
  --reservation-root "$LAB" --mode auto
python3 bridge/experiments/standalone_icb/audit_multicall.py \
  --multicall "$LAB/results/multicall-direct-new" "$LAB/results/multicall-auto-new" \
    "$LAB/results/multicall-auto-2-new" "$LAB/results/multicall-auto-3-new" \
    "$LAB/results/multicall-auto-native-new" "$LAB/results/multicall-wrong-library-new" \
    "$LAB/results/multicall-wrong-client-new" \
  --original "$LAB/results/multicall-original-new" --library "$ARCHIVE"
```

The previous [standalone experiment](STANDALONE_ICB_EXPERIMENT.md) documents
the rendering contract and the ordinary original client. Resolve a failed or
uncertain host to a terminal reservation state before submitting another test.
