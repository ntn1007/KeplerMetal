# Scoped policy for the Apple Release ICB experiment

The same process-local bootstrap now selects either of two signed Release
builds of the **same** Apple CPU ICB sample using an explicit local JSON
policy. It does not need to be recompiled when the selected executable hash
changes. The two unmodified-source builds have different x86_64 `__text`
sections; the second uses Xcode `GCC_OPTIMIZATION_LEVEL=1`. Their bundle
default libraries are byte-identical to the already qualified Release shader.

The policy contains version `1` and up to 16 distinct lowercase SHA-256
executable hashes. The bootstrap reads the policy snapshot, checks the hash
provided by the launcher and requires the signed executable's exact hash to
be listed before its GPU discovery. Library, manifest, device, descriptor and
scope checks remain separately pinned. A policy and its expected hash are
both selected by the caller: this is an integrity and selection mechanism,
**not an independent authorization authority or digital signature**. Being
listed does not certify an arbitrary application's behavior.

## Evidence and limits

Five serialized app processes used one signed bootstrap: one used the A-only
policy and four used the A+B policy, twice for each build. Each captured
64 × 48 drawable contains 15 indirect draws, completed on the GTX, and
matches the archived direct reference byte for byte; the blank reference
differs. Two additional signed processes deliberately used an unlisted B
client or a wrong policy digest. Each exited with status 3 before the
bootstrap's device-discovery call and produced no test capture. This ordering
is checked in the bootstrap source and in its refusal log; it is not a claim
that no unrelated macOS component used the GPU in those processes.

A CPU-only program compiled against the same policy parser accepts three
valid selections and rejects 12 invalid cases, including duplicate entries,
wrong hashes and malformed input. The [audit](apple-release-policy-validation.json)
checks the policy bytes and membership, 17 Apple source/project files against
the separately obtained archive, signed and unsigned Mach-O sections, process
reservations, 75 recorded draws, images, logs and pinned system hashes.
The GPU reservation coordinates laboratory runners, not unrelated processes.

Both builds are the same Apple sample, not independent third-party apps. The
sample's Release assertions, including its Mac 2 check, are disabled; the
device's family is not spoofed. The pipeline remains a separate registered
object built from the original library bytes, and the app's view is adjusted
for capture. This is opt-in process-local adaptation, not transparent macOS
integration or general Metal ICB support. No benchmark, hardware video or
system-driver change is claimed. Earlier preparatory runs used a different
bootstrap and are excluded from the five-render/two-refusal count.

## Reproduce

Obtain the Apple sample, original Release bundle and local fixtures as in
[APPLE_RELEASE_LIBRARY_ICB.md](APPLE_RELEASE_LIBRARY_ICB.md). The two
historical direct/blank controls must match the published earlier audit.
Use fresh output paths, a graphical session and the shared GPU reservation;
resolve unknown process state before retrying.

```sh
LAB='/path/to/nvidia-880m-lab/bridge'
S="$LAB/results/apple-cpu-icb-reference-new"
PROJECT="$S/source/Indirect Command Buffers on CPU.xcodeproj"
A="$LAB/results/apple-release-a-new"
B="$LAB/results/apple-release-b-new"
xcodebuild -project "$PROJECT" -scheme 'macOS - Indirect Command Buffers on CPU' \
  -configuration Release -derivedDataPath "$A" CODE_SIGNING_ALLOWED=NO build \
  > "$LAB/results/apple-release-a-build.log" 2>&1
xcodebuild -project "$PROJECT" -scheme 'macOS - Indirect Command Buffers on CPU' \
  -configuration Release -derivedDataPath "$B" GCC_OPTIMIZATION_LEVEL=1 \
  CODE_SIGNING_ALLOWED=NO build > "$LAB/results/apple-release-b-build.log" 2>&1
APP_A="$A/Build/Products/Release/Indirect Command Buffers on CPU.app"
APP_B="$B/Build/Products/Release/Indirect Command Buffers on CPU.app"
python3 tools/build_from_source.py --out build/apple-policy-new
ARCHIVE="$PWD/build/apple-policy-new"
E=bridge/experiments/apple_release_policy
P="$LAB/results/apple-release-policy-build-new"
python3 "$E/experiment.py" build --lab "$LAB" --archive "$ARCHIVE" --sample "$S" \
  --app-a "$APP_A" --app-b "$APP_B" \
  --log-a "$LAB/results/apple-release-a-build.log" --log-b "$LAB/results/apple-release-b-build.log" \
  --carrier '/path/to/render_state_carrier.metallib' \
  --profiles bridge/experiments/apple_release_library/profiles.json --out "$P"
idx=0
for item in a:a:normal a:ab:normal b:ab:normal a:ab:normal b:ab:normal b:a:denied-client a:ab:wrong-policy-hash; do
  idx=$((idx + 1)); tag=${item%%:*}; rest=${item#*:}; policy=${rest%%:*}; case_name=${rest#*:}
  python3 "$E/experiment.py" run --lab "$LAB" --build "$P" --client "$tag" --policy "$policy" \
    --case "$case_name" --out "$LAB/results/apple-release-policy-$idx-new"
done
python3 "$E/audit.py" --build "$P" --archive "$ARCHIVE" --sample "$S" \
  --app-a "$APP_A" --app-b "$APP_B" --log-a "$LAB/results/apple-release-a-build.log" \
  --log-b "$LAB/results/apple-release-b-build.log" --direct '/path/to/archived-direct-run' \
  --blank '/path/to/archived-blank-run' \
  --runs "$LAB/results/apple-release-policy-1-new" "$LAB/results/apple-release-policy-2-new" \
         "$LAB/results/apple-release-policy-3-new" "$LAB/results/apple-release-policy-4-new" \
         "$LAB/results/apple-release-policy-5-new" "$LAB/results/apple-release-policy-6-new" \
         "$LAB/results/apple-release-policy-7-new" --out "$LAB/results/apple-release-policy-audit-new.json"
```
