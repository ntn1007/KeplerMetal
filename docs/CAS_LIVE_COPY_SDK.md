# Pinned copied-lock CAS profile in the application-local SDK

The [copied-lock-result experiment](CAS_LIVE_COPY_EXPERIMENT.md) now has an
explicit route through `KPCreateCertifiedNativeCASPipeline`. The adapter
accepts a separate `gk104-livecopy-pinned-v1` profile only for the exact
previously qualified library, original native program, repaired program and
metadata fingerprints. It checks the displaced instruction, output register,
trampoline structure, original code and metadata, and the existing device and
driver profile gates. Unknown profiles and changed inputs are refused.

This is an **explicit adapted-client API**, not transparent system integration.
The general SASS recognizer still refuses this shader: its certificate is
identified as a manually GPU-qualified exact profile, not a new automated
dataflow proof. No other program can be inferred supported from the register
numbers or offsets. The existing barrier-trampoline profile continues to use
its previous checks. Certificates and their caller-supplied fingerprints are
not signatures or independent trust boundaries; inputs and the caller must be
trusted. Vendor code and compiled certificates remain local.

## Validation on GTX 880M

Seven signed client processes called the SDK and checked **22,482 CAS operations**
(89,928 output words) across 33-, 128- and 1,024-thread groups, equal and unequal
comparisons, three groups and three seeds. The independent auditor checked
the outputs, sentinels, guards, process receipts, and native-import evidence.
The SDK matched the exact original native constructor payload and metadata;
it restored the constructor after import. This does not read resident GPU
instructions or establish an installed compiler repair.

Four separate controls refused a changed original program, NOP trampoline,
unknown repair profile and modified metadata **before entering the native
constructor**. Auditor mutations of an output value, guard, constructor-entry
receipt and negative profile were rejected. All 11 counted processes were
terminal and nonoverlapping.

A separately prepared copy of the same SDK client repeated the complete
11-process matrix and passed its own independent audit; the two cohorts are
separate executions.

For regression, the former five-function client was rebuilt with the modified
adapter and the previous pinned assets. The independent raw-output verifier
passed its negative and no-dispatch modes, native defect control, and corrected
90-command-buffer run: **106,650 operations** including control operations
matched the CPU oracle. The complete source runtime also rebuilt and linked;
35 focused CAS tests passed. These are bounded tests, not qualification of
all application workloads. No performance comparison or system modification
was made.

[SDK audit](cas-livecopy-sdk-validation.json) ·
[Reproduction audit](cas-livecopy-sdk-reproduction-validation.json) ·
[Auditor mutations](cas-livecopy-sdk-mutation-validation.json) ·
[Previous-profile regression](cas-livecopy-sdk-legacy-validation.json)

## Reproduction

Use the existing isolated lab and retained prerequisites described in the
[original experiment](CAS_LIVE_COPY_EXPERIMENT.md), including the exact
compiler capture and local assembler/decoder. The preparer checks their hashes
and writes the proprietary certificate only to the fresh lab output. The
runner uses a cooperative lease and never kills or automatically retries a
child. A nonterminal process must be resolved before another test. The audit
pins this machine's observed GPU registry ID.

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
REPO='/path/to/KeplerMetal'
WORK="$LAB/results/cas-livecopy-sdk-new"
python3 "$REPO/bridge/experiments/cas_livecopy/prepare_sdk.py" --lab "$LAB" --out "$WORK"
python3 - "$WORK" <<'PY'
import base64,hashlib,json,sys
from pathlib import Path
p=Path(sys.argv[1]); original=json.loads((p/'certificate.json').read_text())
c=dict(original);c['repair_profile']='unqualified-other'
(p/'bad-profile.json').write_text(json.dumps(c,indent=2)+'\n')
c=dict(original);b=bytearray(base64.b64decode(c['native_metadata_base64']));b[100]^=1
c['native_metadata_base64']=base64.b64encode(b).decode()
c['native_metadata_SHA256']=hashlib.sha256(b).hexdigest()
(p/'bad-metadata.json').write_text(json.dumps(c,indent=2)+'\n')
PY
cd "$LAB"
export KM_CAS_WORK="$WORK" KM_CAS_CERT="$WORK/certificate.json"
RUNNER="$REPO/bridge/experiments/cas_livecopy/run_no_kill.py"
python3 "$RUNNER" negative_native_pin 33 1 negative-pin-v1-l33-2
python3 "$RUNNER" negative_sdk_trampoline 33 1 negative-trampoline
KM_CAS_CERT="$WORK/bad-profile.json" python3 "$RUNNER" negative_sdk_certificate 33 1 negative-profile
KM_CAS_CERT="$WORK/bad-metadata.json" python3 "$RUNNER" negative_sdk_certificate 33 1 negative-metadata
python3 "$RUNNER" native_repaired 33 1 repaired-v1-l33-2
python3 "$RUNNER" native_repaired 33 0 repaired-v0-l33
python3 "$RUNNER" native_repaired 128 0 repaired-v0-l128
python3 "$RUNNER" native_repaired 128 1 repaired-v1-l128
python3 "$RUNNER" native_repaired 128 1 repaired-v1-l128-repeat
python3 "$RUNNER" native_repaired 1024 0 repaired-v0-l1024
python3 "$RUNNER" native_repaired 1024 1 repaired-v1-l1024
python3 "$REPO/bridge/experiments/cas_livecopy/audit_sdk.py" --work "$WORK" --out "$WORK/audit.json"
python3 "$REPO/bridge/experiments/cas_livecopy/mutation_sdk_audit.py" --work "$WORK" --out "$WORK/mutation-audit.json"
```

For the earlier SDK regression, use `cas_sdk_source_overlay.py` to create a
fresh overlay, run the overlay's `build_native_cas_sdk_module.py` using the
retained `cas-dynamic-neighbor` generated assets with
`--require-decoder-evidence`, then run `cas_sdk_qualification.py build` on
that module. `legacy_regression.py` takes that build and runs each of
`negative`, `prepare`, `native`, and `execute` under the same lab reservation;
`audit_legacy.py` independently rechecks all four output directories. Existing
fixtures and manifests are not repinned.
