# Opt-in CAS bootstrap with a local client allowlist

The [unified CAS experiment](STANDALONE_CAS_UNIFIED.md) previously embedded one
client hash when compiling the bootstrap. This version reads an explicit local
JSON policy and checks its caller-supplied SHA-256 before accepting an exact
client executable hash from its allowlist. The bootstrap remains tied to the
previously qualified shader library, manifest, certificates, GPU and driver.
The policy may list at most 16 distinct lowercase SHA-256 values. The same
signed bootstrap was tested with a policy containing client A and then a
policy containing clients A and B, without rebuilding the bootstrap.

This is an **opt-in process-local experiment**, not transparent support for
ordinary applications. The tested clients are two differently signed builds
of the **same purpose-built source**, not two independent third-party apps.
Both use the same certified library and mixed factory sequence. The experiment
runner accepts its fixed test clients. A newer [scoped launcher](CAS_LAUNCHER.md)
accepts an explicitly selected allowlisted client; other applications have not
been qualified. A client hash in a policy does not make its shaders safe or
certify its behavior.

The policy hash is supplied by the launching process. It checks the policy
snapshot against that supplied value; it is **not a digital signature or an
independent authorization boundary**. A caller able to choose both the
policy and its expected hash can choose another list. The launch mechanism and
policy must be trusted, and the existing exact shader certificates and
per-profile GPU qualification remain necessary. Hardened applications,
concurrent construction, other libraries and system-wide use are unqualified.

## GTX results

Two native processes, one for each test binary, reproduced **56,808 expected
incorrect CAS words**. Four opt-in processes, two for each binary, produced
**142,200 CPU-verified CAS operations**, including the unmodified comparand
controls. Each host used the same 30-dispatch mixed-factory matrix and checked
guards. The same selected reflection fields matched across all six hosts; full
reflection is not claimed. No performance benchmark was performed.

Client B was rejected with the A-only policy and accepted with the A+B policy.
A policy whose bytes changed without a corresponding expected hash and a
modified client or certificate were rejected before user dispatch. A foreign
library and nondefault descriptor stayed native without user dispatch. Twelve
signed processes were terminal and nonoverlapping under the cooperative lab
reservation. The [audit](standalone-cas-allowlist-validation.json) rechecks
policy selection, source and binary hashes, process receipts and CPU outputs;
eight offline mutations plus a modified reflection field were rejected. The
reservation does not exclude WindowServer or unrelated processes.

An earlier build failed because of a source variable-name collision. In a
subsequent build, client B was signed under a different executable basename;
re-signing the copied `application` changed its hash, so the policy correctly
refused it. That process was terminal and dispatched no user shader. The final
builder signs both variants under the launch basename before recording their
hashes. These failed attempts are retained locally and excluded from the
counts above. Signing identity and executable bytes must be requalified after
any change.

## Reproduction

Use the exact qualified CAS `SDK`, original `SHADER`, common lab reservation
`LAB`, and current verified GTX registry ID `RID`. The builder creates and
signs both client variants and the two policies. Choose fresh output paths and
stop if a process or reservation is unresolved. No Apple or NVIDIA binary is
published.

```sh
EXP=bridge/experiments/standalone_cas_allowlist
python3 "$EXP/experiment.py" build --sdk "$SDK" --shader "$SHADER" --out "$LAB/results/cas-allowlist-build-new"
for item in native-a:1 native-b:1 optin-a:1 optin-a:2 optin-b:1 optin-b:2 denied-b:1 wrong-policy:1 wrong-library:1 wrong-descriptor:1 wrong-client:1 wrong-cert:1; do
  mode=${item%:*}; n=${item#*:}
  python3 "$EXP/experiment.py" run --build "$LAB/results/cas-allowlist-build-new" \
    --out "$LAB/results/cas-allowlist-$mode-$n" --reservation-root "$LAB" --registry-id "$RID" --mode "$mode" || break
done
python3 "$EXP/audit.py" --build "$LAB/results/cas-allowlist-build-new" \
  --runs "$LAB/results/cas-allowlist-native-a-1" "$LAB/results/cas-allowlist-native-b-1" \
    "$LAB/results/cas-allowlist-optin-a-1" "$LAB/results/cas-allowlist-optin-a-2" \
    "$LAB/results/cas-allowlist-optin-b-1" "$LAB/results/cas-allowlist-optin-b-2" \
    "$LAB/results/cas-allowlist-denied-b-1" "$LAB/results/cas-allowlist-wrong-policy-1" \
    "$LAB/results/cas-allowlist-wrong-library-1" "$LAB/results/cas-allowlist-wrong-descriptor-1" \
    "$LAB/results/cas-allowlist-wrong-client-1" "$LAB/results/cas-allowlist-wrong-cert-1"
python3 "$EXP/mutation_audit.py" --optin "$LAB/results/cas-allowlist-optin-a-1"
```

Policy and bootstrap validation affect only the explicitly launched child. No
installed driver, system framework, OCLP configuration or firmware is changed.
