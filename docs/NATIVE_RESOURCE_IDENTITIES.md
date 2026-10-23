# Native resource IDs and the remaining ICB compiler boundary

The existing restored stack already supplies usable texture and sampler
`gpuResourceID` values. The reference GTX executes an ordinary NVIDIA-compiled
shader with these values written directly into a 24-byte argument structure,
along with a buffer's `gpuAddress + 32`. No KeplerMetal runtime archive,
interposition, NAK program, private instruction import or system change is used.
This qualifies an existing native capability; it does not add or repair a getter.

Apple documents direct resource-handle writes as part of the
[Metal 3 argument-buffer interface](https://developer.apple.com/documentation/metal/managing-groups-of-resources-with-argument-buffers).
The test compares this path with the native function argument encoder and with
independent CPU results. It does not infer support from an API selector or a
nonzero handle alone. The handles are opaque; copying arbitrary encoded words
or inventing an ICB ID is not a replacement for an implemented shader/runtime
contract.

## Actual qualification

macOS 26.7.1 / 25G241, SDK 26.2, clang 17, x86_64, GTX 880M PCI `10de:1198`;
the installed driver has exact SHA-256
`e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645`.
The three builds compile the same source using `macos-metal2.3`, `metal3.0`
and `metal4.0`. All three libraries load, create native pipelines and execute
the tested operations. This is not Metal 3/4 feature conformance: the kernel
uses operations already available in the older language subset, and it does
not instantiate Metal 4 command queues, argument tables or pipelines.

| Requested source standard | Actual tested metallib SHA-256 |
| --- | --- |
| `macos-metal2.3` | `3c08478ac1a0cf12ab7a236408d21f4f23e522b9b4c990fce240911e3aeecde2` |
| `metal3.0` | `b410eb61d41b12579c4d596c1f83b44ba1d51e5ff007a9f0ae0d547cea39f322` |
| `metal4.0` | `229d4f095d60b00dc01845a6aa2343d345f388e2b18e4e7624b4a0140a4167ee` |

The final matrix comprises 41 signed terminal nonoverlapping processes, with
90 user compute dispatches in 108 command buffers. The portable auditor checks
48,672 uint32 values, including the expected alternate-resource and no-dispatch
controls, and 27,648 guard bytes. Eighteen native/direct raw-output pairs match
byte for byte. The controls retain 26,232 expected word differences from the
baseline. Each execution process uses counts 16/65/257, with two fresh processes
per mode and standard. All 87 system references remain unchanged. The common
seven-object runtime is unchanged from the previous milestone; it is not linked
into these clients. [Machine-readable results](native-resource-identity-validation.json).

The shader samples an RGBA8Unorm texture, queries width/height/mip count and
combines the result with GPU-buffer input and execution witnesses. It tests a
plain 4x4 texture, a 4x4 view restricted to mip 1 of an initialized 8x8 parent,
nearest filtering and clamp/repeat addressing outside the normalized range.
The alternate texture, sampler and buffer are all valid retained resources,
declared resident before dispatch. They are intentional data-dependence
controls, not invalid GPU handles. The no-dispatch path checks the untouched
initialized output. The host computes its oracle only after readback and never
uploads expected result values.

The native encoder and the direct-ID structure are not always byte-identical:
the tested texture's upper encoded word differs, and the sampler's upper word
matches the buffer's initialization marker. Both paths nevertheless produce
the same checked GPU results. That observation is bounded to these formats,
views and shader operations; it is not an undocumented universal encoding ABI.

## ICB: two actual software boundaries

| Layer | Observed native behavior | Consequence |
| --- | --- | --- |
| Device argument encoder | Pointer, texture and sampler each occupy 8 bytes; ICB and compute-pipeline descriptor kinds occupy 0 bytes | The native encoder does not provide these command-resource layouts |
| Public ICB factory | Compute and render creation reach missing internal `newIndirectCommandBufferWithDescriptor:maxCount:options:` | Object creation/runtime behavior needs implementation |
| Function argument encoder | A normal MSL kernel containing a `command_buffer` gets an encoder with length 0 | The missing kind is also visible through function metadata |
| NVIDIA pipeline compiler | The library and function load, but PSO creation returns `CompilerError`, code 2: `Unsupported indirect argument kind "air.command_buffer"` | The first compiler refusal is the argument kind, before any dispatch |

The ICB compiler probe only calls `compute_command.reset()` and never creates
a command queue or dispatches it. This is not proof that the reset intrinsic
would compile or execute after fixing metadata: downstream command intrinsic
support is still unqualified. The expected refusal has its own explicit oracle;
an unrelated file error, successful PSO or changed encoder length is not silently
treated as the same result.

Apple's [GPU ICB workflow](https://developer.apple.com/documentation/metal/encoding-indirect-command-buffers-on-the-gpu)
requires an ICB argument representation, resource residency and actual command
encoding/execution. A new getter alone cannot provide that workflow. The existing
CommandIR backend remains a bounded alternative with a distinct ABI; these
observations do not turn its context pointer into an Apple native ICB identity.

## Source-only reproduction

Xcode's Metal toolchain is the only shader compiler needed here. No archived
shader, driver download, Mesa library, prebuilt runtime or remote worker is used.
Set `KP_WORK` to a new output directory and `KP_LAB` to the existing shared
reservation root for this physical GPU. Use serial launches and new paths:

```sh
set -e
mkdir "$KP_WORK"
for version in 23 30 40; do
  case "$version" in
    23) standard=macos-metal2.3 ;;
    30) standard=metal3.0 ;;
    40) standard=metal4.0 ;;
  esac
  python3 -B bridge/tools/public_native_resource_identity.py build \
    --standard "$standard" --out "$KP_WORK/build-$version"
  mkdir "$KP_WORK/accepted-$version"
  if [ "$version" = 23 ]; then
    for mode in inspect prepare; do
      python3 -B bridge/tools/public_native_resource_identity.py run \
        --build "$KP_WORK/build-$version" --out "$KP_WORK/accepted-$version/$mode" \
        --reservation-root "$KP_LAB" --mode "$mode"
    done
  else
    python3 -B bridge/tools/public_native_resource_identity.py run \
      --build "$KP_WORK/build-$version" --out "$KP_WORK/prepare-metal$version" \
      --reservation-root "$KP_LAB" --mode prepare
  fi
  for repeat in 0 1; do
    for mode in native direct wrong_texture wrong_sampler wrong_buffer no_dispatch; do
      python3 -B bridge/tools/public_native_resource_identity.py run \
        --build "$KP_WORK/build-$version" \
        --out "$KP_WORK/accepted-$version/$mode-$repeat" \
        --reservation-root "$KP_LAB" --mode "$mode"
    done
  done
done
python3 -B bridge/tools/public_native_resource_identity.py run \
  --build "$KP_WORK/build-23" --out "$KP_WORK/icb-compile-qualified" \
  --reservation-root "$KP_LAB" --mode icb_compile
python3 -B bridge/tools/audit_native_resource_identity.py "$KP_WORK" \
  --out "$KP_WORK/identity-audit.json"
```

The ICB diagnostic always uses MSL 2.3, independent of the selected texture-test
standard. The old spelling `macos-metal3.0` is invalid in this toolchain; its
preserved preliminary failure is a syntax error, not a Kepler limitation. Metal
3.0 and 4.0 use the platform-neutral spellings shown above. Preliminary small
texture tests and the earlier standalone ICB observer are excluded from the
final matrix. All executable, source, shader and raw-output hashes are recorded;
no compiled payload is included in the repository.

## Next implementation target and limits

Preserve the working native texture/sampler path. For ICB work, investigate a
native-compiler lowering of the supported public MSL command operations to the
already-defined, validated record ABI, then connect stable identities, resource
ownership and execution. Such a lowering must preserve the command contract and
be GPU-qualified before any compatibility claim. The compiler's current refusal
is not evidence of a missing Kepler instruction or hardware limit.

No native ICB PSO, ICB execution, complete Metal 3/4 support, system-wide API
integration, physical VRAM accounting or speedup is established by this matrix.
Other texture formats, array/cube/multisample resources, arbitrary views and
command operations remain outside this cohort. M1 reference execution and new
hardware-video tests were not run. Qwen jobs: none.
