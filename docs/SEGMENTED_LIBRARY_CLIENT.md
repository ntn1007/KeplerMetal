# A separate Metal client with a segmented certified library

A separately written public-Metal client loads the already certified library as three independently allocated `dispatch_data` segments and runs `sdk_cas_noise` using a shared output buffer. The client imports no KeplerMetal symbols. The existing scoped launcher applies the unchanged, qualified data-library bootstrap by explicit opt-in and an allowlist entry for this client's signed hash. This qualifies an additional client source and segmented input; it is still a purpose-built client, not an independently supplied application.

The bootstrap maps and checks all incoming library bytes against the same certified snapshot. A different valid segmented library is passed to the original factory. Exact shader certificates, the installed driver profile, GPU and the trusted local policy still constrain this experiment; it does not make arbitrary applications or libraries work automatically. The user controls both the policy and its hash, so this is a snapshot check, not an independent authorization boundary.

## Evidence on the GTX 880M

Five signed processes ran without overlap under the cooperative GPU reservation: one foreign-library construction control, two native baselines and two opt-in executions. Each client reports three input regions using `dispatch_data_apply`. The foreign library reached native pipeline construction without a user dispatch or repair.

The two opt-in executions produced **42,660 correct CAS operations over 36 command buffers**. The two native executions produced **42,606 incorrect expected-value words** in the same shader. A CPU oracle checks all four output words, successful CAS counts, final values, the neighboring shared-memory sentinel and the buffer guards. Inputs cover source-level indices 0–3; they do not independently trace physical GPU addresses.

The auditor checks signed binaries and frozen inputs, argument hashes, per-process terminal reservations, constructor proof and all raw outputs. Copies with corrupted output, guard, data-path trace or reservation state were rejected; an unchanged copy passed. [Audit](segmented-library-client-validation.json) · [Mutation checks](segmented-library-client-mutation.json). No resident-code readback or performance benchmark was performed. The installed system, driver and OCLP were not modified.

## Reproduction

First build and qualify the exact `QUALIFIED_BUILD` described in [the URL/data experiment](STANDALONE_DATA_CAS.md). The builder pins that bootstrap and its assets to the previously published qualification; a different profile requires new qualification. Use the existing laboratory reservation root `LAB` and fresh directories. The launcher validates the policy, signatures, profile and asset hashes; the audit additionally pins the registry ID from this reference boot. A changed registry ID requires review of the audit rather than a silent repin.

```sh
set -e
EXP=bridge/experiments/segmented_library_client
BUILD="$LAB/results/segmented-client-build-new"
python3 "$EXP/build.py" --qualified-build "$QUALIFIED_BUILD" --out "$BUILD"
BOOT_SHA=$(shasum -a 256 "$BUILD/assets/bootstrap.dylib" | awk '{print $1}')
POLICY_SHA=$(shasum -a 256 "$BUILD/policy.json" | awk '{print $1}')
LAUNCH=bridge/tools/launch_certified_cas.py
for item in foreign:1 native:1 optin:1 optin:2 native:2; do
  mode=${item%:*}; n=${item#*:}; ROOT="$LAB/results/segmented-client-$mode-$n"
  mkdir "$ROOT-output"
  if [ "$mode" = foreign ]; then RUN=optin; LIB=wrong.metallib; CLIENT=construct; else RUN=$mode; LIB=cas_client.metallib; CLIENT=run; fi
  python3 "$LAUNCH" --executable "$BUILD/application" --bootstrap "$BUILD/assets/bootstrap.dylib" \
    --bootstrap-sha256 "$BOOT_SHA" --assets "$BUILD/assets" --policy "$BUILD/policy.json" \
    --policy-sha256 "$POLICY_SHA" --reservation "$LAB" --receipt "$ROOT" --mode "$RUN" \
    -- "$BUILD/assets/$LIB" "$ROOT-output" "$CLIENT"
done
python3 "$EXP/audit.py" --build "$BUILD" --foreign "$LAB/results/segmented-client-foreign-1" \
  --native "$LAB/results/segmented-client-native-1" "$LAB/results/segmented-client-native-2" \
  --optin "$LAB/results/segmented-client-optin-1" "$LAB/results/segmented-client-optin-2" \
  --out "$LAB/results/segmented-client-audit-new.json"
python3 "$EXP/mutation_audit.py" --build "$BUILD" --foreign "$LAB/results/segmented-client-foreign-1" \
  --native "$LAB/results/segmented-client-native-1" "$LAB/results/segmented-client-native-2" \
  --optin "$LAB/results/segmented-client-optin-1" "$LAB/results/segmented-client-optin-2"
```

The GPU reservation coordinates participating test runners, not WindowServer or unrelated workloads. Compiled vendor programs, signed executables and private captures stay in the laboratory and are not published.
