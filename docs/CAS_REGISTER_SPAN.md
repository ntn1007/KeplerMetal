# CAS recognizer: full vector register spans

The offline native CAS structural recognizer now applies its existing register-index limit to **every register in a decoded `d` or `q` operand**, rather than just the printed base register. For example, its register parser expands `$r23d` to registers 23 and 24. A synthetic listing with that operand previously passed the structural check because the base was 23; it now fails the existing floor-24 policy. A synthetic in-range `$r20q` remains accepted and reports register 23 as its maximum.

These synthetic listings test the structural function in isolation. Their fabricated instruction words are not demonstrated valid Kepler instructions, would not pass the separate pinned-decoder reproduction check, and were never sent to the GPU. No corresponding real shader failure or security exploit has been established. This is a conservative correction to the project's candidate filter, not a system-driver or Metal compiler fix. It does not prove that this filter understands all instruction semantics or that arbitrary shaders are safe.

## Evidence

The [offline audit](cas-register-span-offline-validation.json) runs the exact previous recognizer against three synthetic listings and checks the new outcomes. It also reproduces the pinned decoder's listings for the four previously captured native candidates and verifies their complete structural results are unchanged. That offline comparison does not itself execute a shader.

A fresh SDK was then regenerated with the updated recognizer. Six signed, serial GTX processes include negative and no-user-dispatch preparation controls, two native baselines and two repaired runs. Across the five shader functions the repaired runs check **213,300 CAS operations / 853,200 output words** against the CPU oracle. The dynamic-address function alone contributes **42,660 correct operations**; its native controls retain **42,606 incorrect expected-value words**. A separate rebuild has identical tested module-object and client executable bytes; the rebuild itself was not run on the GPU. [GPU audit](cas-register-span-gpu-validation.json).

The tested SDK remains an opt-in adapted-client experiment. Existing historical certificates and already built bootstraps are not silently revoked or requalified by this source change; a newly generated policy for another shader still requires exact provenance and its own GPU qualification. No benchmark or speedup is claimed.

## Reproduction

Use the pinned iMac, existing laboratory dependencies and cooperative reservation from [CAS_DYNAMIC_SLOT.md](CAS_DYNAMIC_SLOT.md). Keep outputs fresh and resolve any nonterminal process before proceeding. Obtain the previous original source from the public commit, without replacing the current source:

```sh
set -e
LAB='/path/to/nvidia-880m-lab/bridge'
git show 9ba629b9092877b8c126ddbd3a31c7a85c31b3fa:bridge/tools/recognize_native_cas.py > "$LAB/results/recognizer-before-register-span.py"
python3 bridge/tools/audit_cas_register_span.py \
  --previous "$LAB/results/recognizer-before-register-span.py" \
  --generated "$LAB/results/cas-dynamic-neighbor-overlay-20261028-01/results/generated" \
  --decoder "$LAB/build/envydis-only/envydis/envydis" --out "$LAB/results/register-span-offline-new.json"
```

For a fresh GPU regression, follow the complete SDK overlay, module, six-run and audit commands in [CAS_DYNAMIC_SLOT.md](CAS_DYNAMIC_SLOT.md) using the updated checkout and new output paths. The cited earlier generated cohort is a retained local prerequisite, not distributed with the repository. Proprietary programs and signed captures stay in the laboratory.
