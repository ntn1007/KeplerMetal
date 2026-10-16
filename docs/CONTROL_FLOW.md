# Deep control flow: qualified imports and an unresolved native failure

**Follow-up:** a separate allocation-only experiment corrects the unchanged native65/96 code in the test process. Original/replay/rounding controls still fail; the installed stack and the historical standard matrix below remain unchanged. The exact original iMac metallib also passes the M1 correctness reference with documented group-size adaptations. See [native allocation correction and limits](NATIVE_CONTROL_RESERVE.md).

**The standard qualification is FAIL at native `depth96`.** This milestone is partial. Native programs through source depth64 pass. Separate preserving-import experiments pass for NAK external control-stack requirements of 1,024,1,536,2,048 bytes. The full hardware objective remains incomplete.

## Native failure retained

The generated MSL has 0,4,8,16,24,40,64,96 nested loops. Each loop runs once or twice and descends only on iteration0, so work is linear and at most twice the source depth per invocation. Bounds vary across threads. Input indices stay inside the129-word per-thread stride. There are no barriers or inter-thread data dependencies.

The seven native programs through depth64 passed84 trials, including groups1,31,32,33,64,128,256,512,1024 and selected multiple groups. Native depth96 completed all12 command buffers but left all outputs at A5. This is an actual failure, not an expected successful negative control. Guards and input data are intact.

An instrumented version writes a volatile entry marker before the loops. Its depth0 control passes12 trials. At depth96, all 4,484 invocations write the entry marker and none writes the final result. Thus the instrumented shader starts; neither allocation detection nor command-buffer completion establishes correct completion. Instrumentation changes code and the native spill frame, so this does not uniquely identify the original failure's cause.

Control depth, register spilling and code size grow together. Native depth64 has an856-byte spill frame and28,352code bytes; depth96 has a1,732-byte spill frame and43,328code bytes. The instrumented96 frame is1,740bytes. No physical hardware maximum, general driver incapacity or specific compiler root cause is inferred. The next native investigation must separate these variables or reduce the failing case while preserving its cause.

## Observed allocation contract

Unmodified compiler payloads and4840-byte native variants are captured only inside our own process. Original native constructor inputs/outputs are preserved. Raw captures and GPU code stay local.

For these profiles, metadata word9 equals `64 * word12 + word11`; words12/13 match the private frame, and word14 the native spill size. The decoded allocation word at variant offset40 matches:

```
round_up(native_frame,16) *64 + round_up(metadata_word11,512) +512
```

This is an empirical relation for the recorded profiles, not a universal NVIDIA ABI or a complete interpretation of every field. The importer preserves the actual native allocation. The sole runtime source change exposes decoded allocation/spill values in evidence; it changes no allocation or shader metadata behavior.

## Preserving imports that passed

The existing MRC native-preserving transport pins the original native program, replaces the code and updates only the instruction count. It preserves GPR count and all other native metadata. The client compares decoded allocation and spill values with the native observation before any dispatch. Caller-owned code/original bytes are wiped after PSO creation to check retained ownership.

| AIR/NAK program | Native carrier | Required scratch | Compiler CRS requirement | GPU result |
| --- | --- | ---: | ---: | --- |
| depth0 | depth4 |0|0| PASS |
| depth4 | depth8 |0|0| PASS |
| depth8 | depth8 |0|1024| PASS |
| depth16 | depth40 |100|1536| PASS |
| depth24 | depth64 |296|2048| PASS |
| depth40 | depth96 |668|2560| NOT RUN; carrier's native computation fails |

Five imported programs pass60 trials. Together with the84native trials, the CPU oracle checks215,232 exact uint32 values and53,808 invocation witnesses. Forty-eight no-dispatch controls pass. Passing cohorts have98,304 guard bytes checked and full input comparisons. Five native/AIR program pairs have120 identical input/output files. A depth40 import is created only for a no-dispatch control; that does not qualify GPU execution. The original standard matrix remains failed, alongside the separate selected experiments.

The source-depth64/96NAK programs also compile offline: they require4,096/5,632CRS bytes. They were not dispatched. The96program has86,720code bytes, exceeding the current64KiB import policy; that policy is not asserted as a hardware limit.

On the same thread/process, a control import followed by a descriptor import preserves106,650 correct CAS operations over90 submissions and all 8 rejection controls. This tests transport cleanup, not a general compiler repair. Other historical runtime suites are not automatically inherited by this new archive.

## Artifacts and reproduction

Runtime archive SHA256: `63840c89786b0ad9c862d119335efb80e44cbc9cf54d8a00deca7c12c41ec1de`. Default MSL SHA256: `2fcb68ca33362c87492a7ab46f6fe0b8a4fe9731e9879c902a553f855a31b02d`. Programs manifest SHA256: `df123d98b8ef2e918125f7b98d549cb514f16f7148fd160dedae5e6a2fb3df96`.

Reference macOS26.7.1 build25G241,GTX880M GK104/SM30,SDK26.2,Appleclang17. Mesa26.2.4 extracted tree and OpenNVDA reference `da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5`; effective compiler sources and all 11 linked archives are hashed. Mesa's upstream reference `96cb43121031992b85767f9c1be8f3f48e22b1d2` is not presented as a local checkout commit. Original vendor sources and system components are unchanged. No REA engine evidence is claimed: these are own-process constructor observations and envytools decoding.

The native-only probe can be built from the public text with the licensed Metal toolchain, then launched explicitly through the shared lab reservation. From `bridge/`, use new output directories:

```sh
mkdir -p results
python3 tools/build_control_flow_probe.py --out results/control-native-build
python3 tools/run_command_ir_runtime.py --build results/control-native-build --out results/control-native64 --mode depth64
python3 tools/verify_control_flow.py results/control-native64
# Retain the expected current failure; do not convert it into a passing case.
python3 tools/run_command_ir_runtime.py --build results/control-native-build --out results/control-native96 --mode depth96
python3 tools/verify_control_flow.py results/control-native96
```

Build with `--entry-witness` to reproduce the diagnostic variant. Reference device/driver/registry pins remain strict; a different machine needs its own qualification. All GPU launches from every checkout must share one designated reservation root; the lease does not exclude WindowServer or arbitrary applications.

The advanced import builders retain existing lab prerequisites rather than bundle binaries: `build_control_flow_programs.py` uses the frozen AIR frontend build, `build_control_flow_import_probe.py` selects observed allocations, and `qualify_control_flow.py` runs the full matrix by default. Its explicit `--modes` option runs selected experiments and records `full_standard_matrix=false`. `verify_control_flow_delivery.py` audits the fixed current lab layout and preserves native96failure. See [dependencies](DEPENDENCIES.md) and [AIR/resource contract](AIR_LOCAL_MEMORY.md); no complete clean-checkout import bootstrap is claimed.

The [validation summary](control-flow-validation.json) is not an independent hardware attestation. There is no new M1 reference, performance benchmark, speedup, full Metal-family conformance or installed-driver replacement. The83tracked system files and OCLP remain unchanged.

The separately rebuilt public seven-object archive `30fa23e20a944d1a962ff27d3f63d2fcef5d285cebde108de59bbdea76b7fdf3` passed the full archive/CPU link check and12 imported depth24trials, plus12 depth40 no-dispatch controls. Its complete matrix was NOT RUN; it does not inherit the lab archive’s qualification or resolve the native96failure. All smoke executions used the original laboratory reservation root.
