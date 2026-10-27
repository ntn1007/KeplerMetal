# Scoped launcher for certified native CAS clients

`bridge/tools/launch_certified_cas.py` starts one explicitly selected, signed
client with the existing process-local CAS bootstrap. It checks the client's
allowlist entry, supplied policy and bootstrap SHA-256, the library and
certificates, code signatures and the exact qualified machine profile before
launch. GPU work is serialized with the cooperative lab reservation. It does
not change or re-sign the selected application, nor change the installed
macOS driver, OCLP, a framework or firmware.

This is an **opt-in experimental launcher**, not a general application fix.
The bootstrap and certificates cover a specific library, shader profiles,
GPU and driver. The client must actually load and use those supported shaders;
merely starting successfully does not prove that a repair was applied.
Hardened applications, arbitrary applications and libraries, other devices,
and transparent system integration have not been qualified. A caller-supplied
hash checks a snapshot; it is not a signature or an independent authorization
boundary. The trusted user controls both the policy and its expected hash.
Inputs must remain trusted and unchanged while launching; these checks are not
a security boundary against a concurrent writer.

## Reproduce

Build and qualify the exact SDK, certified library, signed bootstrap, client and
policy as described in [the allowlist experiment](STANDALONE_CAS_ALLOWLIST.md).
Set the variables below to those local artifacts and to the existing common lab
reservation. Use a new receipt path for each launch. This example runs the
purpose-built client; the arguments after `--` belong to that client, and will
differ for another program.

```sh
APP="$BUILD/application"
ASSETS="$BUILD/assets"
BOOT="$ASSETS/bootstrap.dylib"
POLICY="$ASSETS/policy-a.json"
BOOT_SHA=$(shasum -a 256 "$BOOT" | awk '{print $1}')
POLICY_SHA=$(shasum -a 256 "$POLICY" | awk '{print $1}')
OUT="$LAB/results/my-cas-output"
mkdir "$OUT"
python3 bridge/tools/launch_certified_cas.py \
  --executable "$APP" --bootstrap "$BOOT" --bootstrap-sha256 "$BOOT_SHA" \
  --assets "$ASSETS" --policy "$POLICY" --policy-sha256 "$POLICY_SHA" \
  --reservation "$LAB" --receipt "$LAB/results/my-cas-receipt" --mode optin \
  -- "$ASSETS/cas_client.metallib" "$OUT" run
```

Use `--check-only` to check input identity, signatures, certificates and the
current machine profile without reserving the GPU or starting the client. It
does not establish GPU execution or successful bootstrap injection. `--mode
native` provides a matching unmodified client run and still checks the same
inputs. The launcher removes inherited `DYLD_` and `KM_` variables from the
child before configuring the requested mode. It records argument hashes rather
than arguments, but the client's stdout and stderr are saved locally and may
contain private data; the receipt directory and logs have restricted access.

The launcher waits for the selected process and does not impose a timeout or
kill it. If interrupted, do not assume the GPU reservation is clear: inspect
the child and resolve the common reservation according to the lab procedure.
The reservation coordinates cooperating tools; it does not stop WindowServer
or unrelated GPU workloads.

For the six-host audit, name each receipt and its corresponding client output
`cas-launcher-v3-<mode>-<client>-<iteration>` and the same name with `-output`
appended. Run the native A/B hosts once and opt-in A/B twice, with the A-only
policy for A and A+B policy for B. Then verify the saved outputs and receipts
without dispatching another GPU workload:

```sh
python3 bridge/tools/audit_cas_launcher.py --build "$BUILD" --receipts \
  "$LAB/results/cas-launcher-v3-native-a-1" \
  "$LAB/results/cas-launcher-v3-optin-a-1" \
  "$LAB/results/cas-launcher-v3-native-b-1" \
  "$LAB/results/cas-launcher-v3-optin-b-1" \
  "$LAB/results/cas-launcher-v3-optin-a-2" \
  "$LAB/results/cas-launcher-v3-optin-b-2" \
  --out "$LAB/results/cas-launcher-v3-audit.json"
```

The auditor is intentionally pinned to the reference run's GPU registry ID,
selected matrix and receipt names. A later boot or changed inputs require the
identity and assumptions to be reviewed, not silently accepted.

## Qualification on the reference GTX 880M

The [audit](cas-launcher-validation.json) records six serial client processes:
one native and two opt-in runs for each of two signed builds of the **same
purpose-built client**. Each host issued 30 dispatches. The two native runs
reproduced 56,808 incorrect CAS words. The four opt-in runs produced 142,200
corrected and control CAS operations checked against the CPU oracle; guards
and selected reflection fields also matched. Event records identify the four
certified repairs per opt-in host. Corrupting a copied result and changing a
receipt to unresolved were rejected by the audit. Positive preflight and
wrong-client, policy-hash and bootstrap-hash refusals passed; eight offline
unit tests cover preflight and simulated lease outcomes. No performance
benchmark or independent third-party client was tested.

An earlier launcher attempt failed before starting its child because its log
creation call used an unsupported argument. Its reservation reached a terminal
state. The log creation was fixed and the final cohort was rerun after the
last launcher change; earlier trials are not included in these counts.
