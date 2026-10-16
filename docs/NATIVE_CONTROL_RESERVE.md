# Native control allocation: a targeted application-local correction

Two unchanged NVIDIA native programs, `depth65` and `depth96`, produce correct GPU results after increasing their metadata reservation to 4,096. This is a correction inside the experiment's process, using the existing driver and native compiler output. It is not an installed-driver patch, a new Metal API, a general compiler fix or a performance result.

The original failing programs and all failed controls are retained. The earlier standard matrix still fails on the unmodified native96 path; this separate opt-in experiment does not retroactively turn it into a passing qualification. See the [historical control-flow report](CONTROL_FLOW.md) and [recorded verification](native-control-reserve-validation.json).

## What changed, and what did not

`bridge/tools/NativeControlReserveExperiment.mm` intercepts the native variant constructor only while building one PSO in this test application. It pins the GTX 880M, driver SHA-256, constructor owner/type, captured native code hash, container layout and native metadata. The original constructor is restored before any dispatch. Copied input storage is retained with the resulting PSO.

Only metadata words9 and11 may increase. For these profiles word9 is `64 * native_frame + word11`. The original shader bytes, instruction count, GPR count and native spill/frame metadata are preserved. After construction, the probe checks code size, instruction count, GPRs, native spill size and the decoded allocation word. The empirical allocation relation remains:

```
round_up(native_frame, 16) * 64 + round_up(word11, 512) + 512
```

This relation describes the tested profiles, not a complete or universal private ABI. Metadata words2/4 varied between otherwise matching native observations. Their meaning is unknown: their actual incoming bytes are preserved; every other stable word is pinned. No fixed register substitution, instruction patch or NAK program replacement occurs in this experiment.

| Native program | Original word11 | Original decoded allocation | Rounded-word11 control | Reservation4,096 decoded allocation | Numerical result |
| --- | ---: | ---: | ---: | ---: | --- |
| depth65 | 1,584 | 57,856 | 2,048; still 57,856 decoded | 59,904 | 12/12 correct with4,096 |
| depth96 | 2,080 | 114,688 | 2,560; still114,688 decoded | 116,224 | 12/12 correct with4,096 |

At each depth, replaying the copied original payload leaves output unchanged at A5 in all12 trials. Rounding word11 to the next512-byte boundary also fails all12 trials. Merely copying the payload, retaining it or rounding the field therefore does not explain the correction. These are expected failing comparison controls within this allocation experiment; the original native failure remains a real defect.

The4,096 variants pass24 trials:35,872 exact uint32 output values,8,968 per-invocation witnesses and intact inputs/guards. All six allocation cohorts check36,864 guard bytes. Launches include group sizes1,31,32,33,64,128,256,512,1024 and selected multigroup cases. Each process terminates normally and each cooperative reservation reaches terminal state.

Code identity is checked in the constructor input payload, not by an independent capture of resident GPU instructions. The decoded native allocation and GPU output are separate observations. The experiment does not establish a minimal reservation or a unique root cause inside the closed-source compiler/driver.

## Reduction and independent reference

The native boundary is sharper than the earlier0..96 sampling suggested: source depth64 passes, while each sampled depth65..72,80,88,96 fails. Reloading loop bounds does not repair96. These source depths are not asserted as physical hardware stack limits.

Separate native controls work with a104,000-byte sequential-loop program and with register-pressure frames up to4,656 bytes/thread. They exercise different programs, so they do not isolate every interaction. They do rule out treating either a blanket32/64KiB code-size ceiling or the tested spill-frame size alone as the established explanation.

The M1 Max reference passes36 positive and12 no-dispatch trials with the exact same MSL compiled on that machine. A second reference passes another36 positive and12 no-dispatch trials while loading the exact original iMac metallib bytes, SHA-256 `d861a84fc1067c87a23ae73beb2755afc82b6ab28895f869950e315f983b8822`. This second run does not recompile the library frontend on the M1; its host is compiled for arm64. Both references use native Apple GPU execution, not SM30.

The M1 pipeline maximum is384 threads for64/96, so requested512/1024 groups explicitly use1 thread/group there. Inputs, total invocations and CPU semantics match; group geometry is not identical for those cases. This is a correctness reference, not a cross-device speed comparison. Observed M1 host: macOS27.0.1 build26A434, SDK27.0; original shared library frontend: iMac SDK26.2.

## Reproduction from public text

Use the licensed Apple toolchain and the pinned driver described in [dependencies](DEPENDENCIES.md). The native observer additionally needs the locally built envytools `bridge/build/envydis-only/envydis/envydis`. No vendor binary, generated GPU code or raw capture is distributed here.

From `bridge/`, create new directories for every build and run. The native source/host builder is standalone; the allocation builder consumes your own observation rather than an archived shader body:

```sh
mkdir -p results
python3 tools/build_control_flow_probe.py --out results/native-boundary-build --depths 64 65 96
python3 tools/observe_control_flow.py --build results/native-boundary-build --out results/native-boundary-observations

python3 tools/build_native_reserve_experiment.py --native-build results/native-boundary-build --observations results/native-boundary-observations --reserve 4096 --out results/reserve4096-build
python3 tools/run_command_ir_runtime.py --build results/reserve4096-build --out results/reserve4096-depth65 --mode depth65
python3 tools/verify_control_flow.py results/reserve4096-depth65
python3 tools/run_command_ir_runtime.py --build results/reserve4096-build --out results/reserve4096-depth96 --mode depth96
python3 tools/verify_control_flow.py results/reserve4096-depth96
```

Build separate experiments with `--reserve 0` and `--reserve round`, and retain the expected failed numerical results at65/96. Do not map arbitrary exit1 results to success. Unqualified code or metadata must be rejected before dispatch. The experiment is MRC; its test host is ARC. It is not linked into the shared runtime by default.

Every GPU launcher/observer across checkouts must use the same designated lab reservation root. The public scripts default to their own `bridge/` root: when another active lab checkout exists, build and run in that designated root rather than create independent leases. This lease coordinates participating runners only; it does not exclude WindowServer or arbitrary applications.

`prepare_control_flow_reference.py` prepares a source-only bundle for an authorized M1 host. Its `--adapt-local-limit` option records the explicit geometry adaptation. `run_control_flow_reference.py` can compile MSL there or use `--metallib FILE --metallib-sha256 HASH` to load your own privately transferred, verified library. Private SSH configuration is not included. Verify the resulting files with `verify_control_flow.py --apple-reference`.

`verify_native_control_reserve.py` is a read-only audit of the fixed historical lab layout and its retained private files. It recomputes numerical results, reparses native captures, verifies exact manifests, checks the allocation experiment's proof, and rehashes the83 baseline system files plus OCLP. It submits no GPU work. A clean public checkout lacks these binary/result fixtures; the JSON here is a compact source-release summary, not an independent hardware attestation.

## Remaining work

Qualify more native program profiles and explicit rejection controls; determine a conservative allocation contract and investigate the internal cause. Integrating it into the shared runtime needs its own ownership/concurrency and regression qualification. Arbitrary shaders, transparent unmodified-application integration, broader hardware coverage and Metal-family conformance remain open. The installed driver, OCLP and83 tracked system files remain unchanged. No performance benchmark was run.
