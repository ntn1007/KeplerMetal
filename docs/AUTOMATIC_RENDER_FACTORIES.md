# Queue-local automatic render encoders

An opted-in `KPCPUICBScope` can now adapt qualified render encoders created via
ordinary `[commandBuffer renderCommandEncoderWithDescriptor:]` calls on its
own queue. The queue, command buffers and render encoders are adapted as
individual objects; the native shared class implementations are not replaced.
The caller no longer needs to invoke `renderEncoderWithDescriptor:commandBuffer:`
for each qualified pass. The existing explicit method remains available and can
be used after automatic activation.

The test client is a separately compiled, signed dynamic library whose imports
contain no KeplerMetal symbols. Its render code uses public Metal calls to
create a CPU-encoded render ICB, command buffer and encoder, execute a draw and
read back the image. A separate host explicitly installs the scope, enables its
queue-local factories, supplies the scope-owned pipeline and invokes the client.
This is a controlled integration test, not execution of a previously existing
unmodified application. Automatic application bootstrap, ordinary application
pipeline registration and transparent system-wide Metal support remain open.

```objc
// Bootstrap performed by the host; data and queue belong to this scope.
KPCPUICBScope *scope = [KPCPUICBScope installRenderingOnDevice:device
    queue:queue libraryData:carrier expectedSHA256:carrierHash error:&error];
if (!scope || ![scope enableAutomaticRenderEncoderFactoriesWithError:&error]) return;
// Client code can now use ordinary queue/command-buffer/render-encoder calls.
```

Activation is idempotent and limited to the queue associated with that scope.
Another queue and the shared native method implementations remain untouched in
the cases tested. When the automatic mode is not enabled, the old explicit
encoder API behaves as before. Enabling rendering alone leaves ordinary compute
encoders native; the existing compute-only factory path is separately regression
checked. Simultaneous automatic compute and rendering activation in the same
scope is not yet qualified.

For a render pass outside the existing exact profile, the client receives a
queue-local guarded encoder: ordinary native drawing is inherited unchanged,
but both public ICB execution selectors reject project-owned render or compute
ICBs rather than passing those non-native objects to the NVIDIA driver. If an
encoder cannot be safely guarded, creation fails closed. The client must not use
project ICBs after scope restoration; applications must quiesce their encoders
and factory calls before restoring a scope. Arbitrary render passes, concurrent
restoration, and native Apple ICB ABI compatibility are not established.

The test deliberately avoids forwarding a project ICB to a native encoder in the
`no_auto` control. A supported render can use one CPU-created ICB and a scoped
pipeline; this says nothing about arbitrary precompiled GPU-generated ICBs. Native
internal preparation can create additional scoped render encoders, which are
reported separately from client frames. No speedup is claimed.

Two preliminary GPU hosts are kept outside the final cohort: the first lacked a
GPU identity field in its summary; the second produced a correct image but its
frozen oracle expected too few internal encoder events. Both processes ended;
the final builder records identity and distinguishes client encoders from
internal ones. Earlier passes without the guarded fallback are also retained as
exploratory runs and are not counted as final qualification.

On October 27, 2026, an independent audit rechecked 16 ordinary-client hosts
and seven same-runtime regression hosts, all serialized. The 20 client frames
contain 229,376 CPU-checked float channels with exact expected values; 12 frames
execute the scoped CPU-encoded ICB. Native direct reference images and repeats
match byte for byte. Two unsupported-pass cases each refuse both project-render
ICB selectors while retaining native drawing; two live-restoration cases also
refuse both selectors for a synthetic project compute ICB. Two compute regression
runs verify 915,456 exact uint32 results; a third checks 43 factory contracts.
All 366 CPU tests pass locally and from a source export. The exported client and
host rebuild byte-identically and pass two further GPU hosts. Seven independent
offline mutations of pixels, client bytes, encoder class, method state and guard
reason were rejected. [Audit and fingerprints](automatic-render-validation.json).

## Reproduction

Use the supported macOS/SDK/driver profile and a fresh output directory. Each
GPU host is signed and uses the shared laboratory GPU reservation. Do not run
hosts concurrently.

```sh
python3 tools/build_from_source.py --out build/automatic-render-runtime
python3 bridge/tools/public_automatic_render.py build \
  --library "$PWD/build/automatic-render-runtime" --out /absolute/client-build
python3 bridge/tools/public_automatic_render.py run --build /absolute/client-build \
  --out /absolute/results/accepted-auto-01 --mode auto \
  --reservation-root /absolute/common-lab/bridge
```

The mode sets and same-runtime render/compute regressions are listed in
`bridge/tools/audit_automatic_render.py`. It replays each frozen oracle, checks
terminal nonoverlapping receipts, verifies the client signature and dependencies,
and compares the ordinary client images. See the existing quad, fragment and
native library factory documents for their respective regression builders.
