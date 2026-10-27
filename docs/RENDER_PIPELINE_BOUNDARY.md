# Typed render-pipeline boundary

This is a construction-only comparison of the same Metal shaders on the GTX
880M and an Apple M1 Max. It does not submit a command buffer or prove shader
execution, correct rendering, an adapter, Metal conformance or a performance
improvement. The scoped implementation did not yet implement typed
`render_command.set_render_pipeline_state` at the time of this observation;
the later scoped result is described in [the runtime integration](PIPELINE_RUNTIME_INTEGRATION.md).

The shader contains a 16-byte argument struct holding a `command_buffer` at
index 0 and a `render_pipeline_state` at index 1, followed by a triangle draw.
The same source SHA-256 was checked after SSH transfer. On the tested NVIDIA
stack, both render pipeline descriptors constructed successfully, but the
render-pipeline argument descriptor had encoded length 0 and the shader's
function argument encoder had encoded length 0. Creating the compute pipeline
failed with `Unsupported indirect argument kind "air.render_pipeline_state"`.

On the M1 Max with macOS 27.2 build 26B118 and SDK 27.0, the corresponding
descriptor encoded 8 bytes, the function argument encoder had length 16, and
the compute pipeline was created. Encoded words were 0 with indirect-command
support disabled and 1 when enabled. On the GTX both queried resource IDs were
0. **Zero alone is not evidence of a defect:** it also appeared on the M1
pipeline without indirect support. No inference about undocumented Metal ID
semantics follows from these particular values.

Two signed, separately reserved GTX observations of the original host and a
third with explicit encoding attempts agreed on the compiler and encoder
boundary. The M1 comparison uses an ordinary SSH command and self-reported
device name; unlike the GTX, it has no signed-host reservation receipt. Neither
machine dispatched this shader. The frontend's acceptance of a shader under a
given MSL language version does not establish that the driver implements that
Metal version. The failure is a software boundary, not proof that the hardware
cannot perform the desired rendering operation.

An additional signed GTX construction control uses an ordinary struct with
two `ulong` fields instead of Metal command and pipeline types. Its reflected
root and encoder are 16 bytes with alignment 8, and the native compute
pipeline is created. It contains no pipeline-selection operation and was not
dispatched. This shows a possible representation accepted by the compiler; it
does not establish that rewriting the typed program is correct or executable.

## Offline prototype

At the time of this observation, `KeplerPipelineTransitionPlan.h` was an isolated
CPU planning experiment. A later [runtime integration](PIPELINE_RUNTIME_INTEGRATION.md)
connects it to the scoped adapter. In the offline planner, the caller supplies
process-local opaque tokens, not Apple resource IDs. A transition may only
change the pipeline when slot, draw fields, index binding and all vertex and
fragment bindings match. Duplicate tokens, ambiguous transitions, malformed
bindings and tables over the bounded limit are rejected. The eventual runtime
must independently establish object ownership, lifetime, alias safety and
correct GPU execution. These tests alone do not make a new API usable.

## Reproduction

On the GTX machine, choose fresh directories and use its existing common GPU
reservation, even though this probe creates no command buffer:

```sh
python3 bridge/tools/public_native_render_pipeline_probe.py build --out /absolute/build
python3 bridge/tools/public_native_render_pipeline_probe.py run \
  --build /absolute/build --out /absolute/observation \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_native_render_pipeline_probe.py build --plain-root --out /absolute/plain-build
python3 bridge/tools/public_native_render_pipeline_probe.py run \
  --build /absolute/plain-build --out /absolute/plain-observation \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/verify_render_pipeline_plain_root.py /absolute/plain-observation
python3 -m unittest discover -s tests -p test_pipeline_transition_cpp.py -v
```

The host, Metal sources, runtime helper and verification code are frozen and
hashed by the build; the run signs a new copy and audits its receipt. The
reference host is generated from the frozen `src/native_render_pipeline_probe.mm`
by removing `#import "KeplerGPUIdentity.h"` and replacing the Kepler identity
check with `NSDictionary*identity=@{@"reference_device":d.name?:@""};if(!d)return 2;`.
Transfer that host and the two frozen Metal sources to the M1, check their
SHA-256 values on both sides, then execute:

```sh
shasum -a 256 *.metal *.mm
xcrun metal -std=macos-metal2.4 -c render_state_carrier.metal -o graphics.air
xcrun metallib graphics.air -o graphics.metallib
xcrun metal -std=macos-metal2.3 -fmodules=none -c air_render_pipeline_probe.metal -o probe.air
xcrun metallib probe.air -o probe.metallib
xcrun clang++ -O2 -std=c++17 -fobjc-arc native_render_pipeline_probe.mm \
  -framework Metal -framework Foundation -o application
./application graphics.metallib probe.metallib
```

Capture the hash lines and JSON together. Check the frozen GTX receipt and the
reference hashes and output with:

```sh
python3 bridge/tools/verify_render_pipeline_comparison.py \
  --gtx /absolute/observation --reference-input /absolute/reference-input \
  --reference-output /absolute/reference.stdout
```

The recorded output digests are in [the validation record](render-pipeline-boundary-validation.json).
They identify the local artifacts; they are not independently attested M1
measurements. To implement the feature, the next steps include an explicitly
owned two-word argument root, a bounded AIR transformation, resource lifetime
and alias checks, causal negative controls, then a signed GTX render compared
with an independent CPU oracle. Full application integration remains separate.
