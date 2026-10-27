# Experimental standalone Metal client

This branch-B experiment runs an executable built only against public Metal and
Foundation APIs, without linking KeplerMetal, as a separate signed process. An
explicit launcher loads an experimental bootstrap into that process only. The
client calls the standard device, queue, library, pipeline, CPU-encoded render
ICB, command-buffer and render-encoder APIs. It does not call a KeplerMetal API.
This is a purpose-built client, not an independently supplied application.

The bootstrap intercepts device creation for **one exact signed client hash**,
requires a single matching GTX 880M device, verifies a pinned Metal library
snapshot, and activates an existing queue-local rendering scope. For this pinned
client it supplies the one qualified queue and recognizes functions originating
from the verified library. Only the known render pipeline is redirected to the
scope-owned pipeline. The loader and its environment are set only on the child;
no system framework, driver, OCLP configuration or shared native class is
replaced. This is opt-in process-local adaptation, not transparent macOS-wide
integration. Its bytecode, entitlement and shader identities are deliberately
narrow; other executables are refused rather than treated as compatible.

On the tested GTX 880M, the same signed executable rendered a 64×48 RGBA32Float
image directly through native Metal and using the adapted CPU-encoded ICB. Each
image had 12,288 exact expected float channels, intact guard bytes, and an
identical SHA-256. The native ICB control stopped at the missing internal Metal
selector before dispatch. A different library with the same function names was
not registered and its pipeline was rejected by the scope. An altered client
was refused before the scope was installed. All five public-reproduction hosts
terminated and the independent oracle passed. Earlier exploratory runs include
three additional correct ICB outputs. Four offline mutations of a copied result
(pixel, event, bootstrap and reservation state) were rejected.

The first exploratory interposition exited on SIGSEGV before a trace. A later
instrumented run showed that looking up the original symbol using the framework
handle returned the replacement, consistent with recursion; that hypothesis is
not an independently captured stack trace. The final bounded test instead uses
`MTLCopyAllDevices` with an exact single-device identity check. The exploratory
failure and subsequent refusal are retained locally, and no general conclusion
about `dlsym` is needed for the supported test path.

Limits: one command queue, one library, one pipeline, one draw, and a CPU-encoded
ICB. The bootstrap has not been qualified for arbitrary pipeline descriptors,
multiple queues, multi-threaded initialization, GPU-generated ICBs, independent
third-party clients or hardened applications. It substitutes a scoped pipeline;
it does not repair the NVIDIA compiler, install a driver, add Metal 3/4 support,
or demonstrate a speedup. The GPU reservation coordinates project hosts, not
WindowServer or unrelated GPU clients.

## Reproduction on the qualified profile

Build the public runtime first, use a new empty output path, and provide the
same host-wide GPU reservation root used by the other KeplerMetal tests. The
builder checks source snapshots, SDK, architecture and driver profile; it creates
and signs its own binaries locally. No Apple or NVIDIA binary is redistributed.

```sh
python3 tools/build_from_source.py --out build/standalone-runtime
python3 bridge/experiments/standalone_icb/experiment.py build \
  --library "$PWD/build/standalone-runtime" --out /absolute/standalone-build
python3 bridge/experiments/standalone_icb/experiment.py run \
  --build /absolute/standalone-build --out /absolute/direct-result \
  --reservation-root /absolute/common-lab/bridge --mode direct
python3 bridge/experiments/standalone_icb/experiment.py run \
  --build /absolute/standalone-build --out /absolute/icb-result \
  --reservation-root /absolute/common-lab/bridge --mode auto
```

Run `auto-native`, `wrong-library`, and `wrong-client` with separate output
directories for the three negative controls. Their child processes exit 7, 7,
and 3 respectively; the independent oracle checks the specific expected failure
and reports PASS only when the GPU reservation is terminal and all evidence
matches. See [validation fingerprints](standalone-icb-validation.json).
