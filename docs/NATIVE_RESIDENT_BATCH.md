# Explicit resident batches with completion boundaries

`KPResidentBatch` moves the previous client-side wait experiment into an optional
SDK module. The application prepares an immutable plan from its registered
KeplerMetal CPU ICB slots, then asks that plan to encode its own carrier encoder.
The seven common runtime implementations and installed graphics stack are
unchanged. Ordinary Metal concurrent encoders are still not implemented.

The admitted shader profile is deliberately explicit: the published
`observe_a`/`observe_b` library, 17 registers, the retained native 256-byte literal
bank, one group of one thread per entry, and 1–4 entries. The public profile JSON
pins the regenerated metallib. Unknown libraries, shader footprints or geometry
are refused. This is an opt-in SDK prototype qualified by a laboratory client;
it does not qualify ordinary applications or full Metal conformance.

## API and ownership

```objc
KPResidentBatch *batch = [KPResidentBatch prepareScope:scope
    buffer:icb indices:@[@0, @1, @2, @3]
    barrierBefore:[NSIndexSet indexSetWithIndex:2] error:&error];
// Check batch/error. Preparation can submit NOP/copy work, with no user kernel.
// Resetting or changing the original ICB later does not change this snapshot.
id<MTLCommandBuffer>cb = [queue commandBuffer];
NSDictionary *proof = nil;
BOOL encoded = [batch encodeToCommandBuffer:cb evidence:&proof error:&error];
// On failure, discard cb. On success, commit and observe completion normally.
```

The module snapshots record identities and both explicit boundaries and source
slots' `setBarrier` flags. Boundaries use positions in the selected sequence,
so position 2 separates entries 0/1 from entries 2/3. Later `clearBarrier`, reset
or mutation of the caller's arrays cannot alter the prepared plan. The scope
must remain active. The existing transport retains native resource/program
owners through completion. The reception client keeps its plans alive, so
release of the last plan before commit is not separately GPU-qualified here.

The intended completion boundary follows Apple's
[`setBarrier`](https://developer.apple.com/documentation/metal/mtlindirectcomputecommand/setbarrier%28%29)
contract: earlier commands complete before the marked command begins. This
cohort verifies atomic sequence ordering and final results. It does **not**
independently establish arbitrary non-atomic producer/consumer visibility or
the complete Metal memory model.

The known kernels atomically access 12 bytes of sync state, write 32 bytes of
output, and read 16 bytes of configuration. Inside a segment, the planner
allows exact atomic sharing and read/read sharing; it refuses non-atomic
write conflicts, partial atomic overlaps, repeated descriptor state, self
aliases and writes into resident descriptor/constant state. This footprint is
specific to the pinned shader source, not inferred for arbitrary MSL. Config
limits (4,096 polls, 128 arithmetic rounds) are checked again before encoding.
Clients must preserve resource contents until completion, as with Metal.

The module owns creation and `endEncoding` of the native serial carrier. It
verifies the exact resident launch tails, original transport hash, writable
cursor bounds and final wait before changing any word. Only waits immediately
before a barrier-free next entry become `NO_OPERATION`. The terminal wait and
all launch/state words stay exact. Candidate bytes are checked again after
`endEncoding`. Any failure requires discarding the uncommitted buffer.
The actual native `dispatchType` remains serial (`0`); it is not spoofed.

## GPU evidence

Four records have eight disjoint Private allocations: four 4,096-byte descriptor
allocations and four 65,536-byte constant allocations. GPU copies read back each
active 256-byte QMD and every constant byte. Before experimental classes and
after execution, their hashes remain unchanged. Native code and literal-bank
owners are retained; native instruction bytes are not read back by this test.

All source ICB slots are reset before user dispatch. The plans still produce
the correct outputs, using four separate output regions and per-record nonces.
Atomic tags independently describe ordering; the CPU recalculates 128 rounds
of uint32 arithmetic, flags, polling bounds, all guards and parameter padding.

The laboratory cohort contains 108 main trials and 292 correct user dispatches
across five compute processes, plus a zero-user-kernel preparation process.
The CPU auditor checks 82,944 raw sync/output words, 80,284 guard words and
442,368 raw parameter bytes. Ten four-entry batches have all six pairwise
intervals interleaved. Twenty-eight four-entry split batches preserve the
requested midpoint boundary, including source-slot `setBarrier` cases.
Thirteen actual refusal cases run in each successful process. Nine portable
oracle tests cover every four-entry boundary mask, conflicts, corruption and
cross-boundary ordering.

A first segmented launch was refused by the common reservation while the
human administrator port experiment held it. No native child was started.
That nonexecuted attempt is preserved separately; retry followed verified
termination of the administrator helper. It is not counted as a GPU failure
or a successful trial.

The independently rebuilt public artifact has its own results in
[the sanitized validation summary](native-resident-batch-validation.json).
Its complete seven-object core, optional module and native shader are rebuilt
from text. It does not inherit other historical GPU suites.

That separate public qualification passes 62 main trials / 156 user dispatches,
47,616 raw sync/output words, 46,182 guard words and 253,952 parameter bytes.
Its eight four-entry unsegmented batches each have all six pairwise intervals
interleaved; its eight split batches preserve the midpoint. All four processes
(including preparation) terminate normally and restore their scope. The full
portable suite passes 57 tests. The public core archive differs from the lab
archive; the optional object and linked client happen to be byte-identical.

Interleaved intervals do not prove simultaneous instructions or SM occupancy.
Polling work changes with ordering, so these are correctness tests, not a
performance benchmark. No speedup or CPU relief is claimed.

## Source-only reproduction

Use an existing licensed Intel macOS/Xcode/restored-driver installation; see
[DEPENDENCIES.md](DEPENDENCIES.md). Reference compilation used macOS 26.7.1
(25G241), SDK 26.2, Apple clang 17.0.0 and x86_64. No vendor executable,
metallib, captured command stream, personal configuration or credential is
distributed. A different shader hash is refused rather than silently repinned.

```sh
python3 -m unittest discover -s tests -v
python3 tools/build_from_source.py --out build/batch-core
python3 tools/native_resident_batch.py build \
  --core-build build/batch-core --out build/batch-client
```

Those builds execute no GPU work. The common builder snapshots the optional
module's source too, but still compiles its original seven objects. The second
builder compiles the optional ARC object separately, regenerates AIR/metallib,
links the client and freezes source/tool/runtime hashes.

Use the **same existing host reservation root for every checkout and cohort**.
The commands below use `bridge` only for a fresh single-checkout laboratory;
initialize `bridge/results` in that case. An existing lab must replace it with
its current common root. The lease coordinates cooperating lab launchers,
not WindowServer or every GPU client. All output paths must be new.

```sh
mkdir -p bridge/results
python3 tools/native_resident_batch.py run \
  --build build/batch-client --out build/batch-prepare --mode prepare \
  --trials 1 --reservation-root bridge
python3 tools/native_resident_batch.py run \
  --build build/batch-client --out build/batch-serial --mode serial \
  --trials 4 --baseline build/batch-prepare --reservation-root bridge
python3 tools/native_resident_batch.py run \
  --build build/batch-client --out build/batch-segmented --mode segmented \
  --trials 1 --baseline build/batch-serial --reservation-root bridge
python3 tools/native_resident_batch.py run \
  --build build/batch-client --out build/batch-parallel --mode parallel \
  --trials 4 --baseline build/batch-segmented --reservation-root bridge
python3 tools/native_resident_batch.py audit \
  --build build/batch-client --run build/batch-parallel \
  --out build/batch-independent-audit.json
```

`run` explicitly submits GPU work using the immutable signed common launcher.
Each prerequisite is independently re-audited from its raw files on the exact
same build before the next phase. Each experimental process repeats serial
controls first. The final `audit` performs no GPU work. A refusal or uncertain
process is retained and inspected before any further launch.

Next requirements are a separately qualified non-atomic dataflow/visibility
contract, additional native libraries and geometries, and integration with the
ordinary Metal factories. The installed driver and OCLP remain unchanged.
