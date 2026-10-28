# Selected legacy video-provider service

The earlier [input observation](VIDEO_PROVIDER_FIELDS.md) established that, in two controlled legacy AppleGVA calls, the selected entry was nonzero. It did not identify the entry. A new own-process observer now interprets the selected 32-bit entry as an IOKit object only after the old AppleGVA caller path, image UUID, callsite bytes, index, mask and readable array region match the pinned profile.

In **two new hardware-required processes**, the entry is a Mach send right; `IOObjectGetClass` returns `nvAccelerator` and `IORegistryEntryGetRegistryEntryID` returns **4294968416**, the sole GPU accelerator ID independently checked by the build/profile preflight. This ties the selected entry to the GTX accelerator on this boot and on these controlled legacy paths. The observer does not retain or release the borrowed selected right. A separate calibration obtains a known matching service, verifies its class and ID, releases its own acquired right and confirms rejection of a null port. These public IOKit identity queries are not video selectors.

Each request still returns `-12913` and zero images. The experiment explicitly selects the historical 10.13.6 AppleGVA and earlier scoped policy/dependency counterfactuals. It replaces the installed NVIDIA create-stub lookup with a test gate returning 14; it does **not** invoke the Sierra provider. Neither the other array entries nor the right's ownership and lifetime after the call are established. The result does not establish live selector dispatch, hardware video execution, behavior of modern default AppleGVA or driver compatibility.

The [cohort audit](video-provider-service-validation.json) validates frozen source and build, signed process identities, five terminal nonoverlapping receipts, input assets, gate captures and a wrong-name refusal control. A separate software control produces six images equal to 2,764,800 reference bytes. All three hardware-required cases, including the wrong-name control, return `-12913` with zero images. Eight portable unit tests cover this and earlier registration/argument checks, including changed service identity and calibration failure. The cooperative reservation does not exclude WindowServer; the gate's explicit calls are scoped, but unrelated framework initializers are not exhaustively traced. No system component, OCLP or firmware is modified and no speed gain is claimed.

## Reproduction and profile boundary

The recorded build depends on the retained private laboratory, existing pinned AppleGVA 10.13.6, current driver hashes and boot-specific registry ID. The coordinator currently expects `$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge`; its exact build and source are frozen in the manifest. The checker intentionally pins the recorded build hash, so it re-audits this build rather than accepting a freshly rebuilt binary as identical. Rebuilding, changing system files or restarting requires separate requalification and a new audit profile. No Apple or NVIDIA binary is published.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_provider_service
python3 "$EXP/audit.py" --build "$R/video-provider-service-build-20261028-01" \
  --out "$R/video-provider-service-reaudit-new.json" \
  --hosts "$R/video-provider-service-inspect-20261028-01" \
  "$R/video-provider-service-enabled-20261028-01" "$R/video-provider-service-wrong-20261028-01" \
  "$R/video-provider-service-enabled-20261028-02" "$R/video-provider-service-cpu-20261028-01"
python3 -m unittest discover -s tests -p 'test_video_provider_*.py' -v
```

Further work must establish the live method/selector contract and ownership before using this historical provider; these observations do not justify issuing its private commands to the current kernel.
