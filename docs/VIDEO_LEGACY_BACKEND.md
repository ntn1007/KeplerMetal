# Historical legacy-video backend: scoped re-audit

An earlier lab experiment explicitly selected a locally obtained macOS 10.13.6 AppleGVA implementation inside test processes. It also used the previously documented, process-local `IOGVACodec` presence and board-policy counterfactuals. This was **not** the unmodified default modern macOS video path.

In two independent archived hardware-required cases, the original legacy GVA path logged `AVD_api.Create` returning 14. After the return, an own-process observer recorded one matching active backend node whose creation pointer was the installed `GeForceVADriver` export `AVD_CreateAVDAccelerator`. Its exact 11-byte code range at image offset 16290 is an unconditional return-14 stub; the whole installed binary and code range are hash checked. The static provenance for the legacy caller is bound to four complete function ranges and retained REA evidence. The backend node was read after the error: the observation is not a private-entry breakpoint and does not rule out all races. The result identifies a concrete missing-provider candidate on this tested legacy path, not a complete proof that every modern decoder refusal has this cause.

The frozen cohort contains 20 terminal, nonoverlapping processes: 12 hardware-required creates were refused, with zero hardware images; 24 software images match 8,985,600 bytes from independent CPU references. The captures also include typed logging and forwarding controls. No video-engine execution, replacement provider, NVENC support, performance improvement or installed-driver fix was established.

## Re-audit and current profile

On 2026-10-27 the original full historical auditor was attempted again and stopped because a protected component no longer matched its 2026-10-18 inventory. The new [scoped re-audit](video-legacy-scoped-validation.json) checks the frozen source/import closure, all 20 original receipts and their raw numerical outputs against the historical audit, the four pinned static proofs and the installed provider's exact identity. It uses the **same pinned historical auditor functions**, not an independent hardware execution. It separately compares the original 83-file inventory with the current machine: five files differ, as already discussed in [profile drift](VIDEO_PROFILE_DRIFT.md). It makes no present-day claim that those 83 files are unchanged.

The separate static mapping `video-session-inner-stubs-20261027-01.json`, kept in the lab, maps nine calls in the newer AppleGVA candidate-enumeration region to five static GOT targets. These include logging, string comparison and memory-management functions. Static targets do not establish that this region executed or caused the current refusal; the runtime branch remains unresolved.

## Reproduction from the existing private laboratory

No Apple or NVIDIA binary is distributed. The following rechecks existing artifacts and creates a fresh JSON report without invoking the native test host or video engine:

```sh
python3 bridge/experiments/video_legacy/reaudit.py \
  --lab "$LAB" --out "$LAB/results/video-legacy-scoped-reaudit-new.json"
```

It requires the exact frozen lab source hashes and historical artifacts. Missing or changed inputs are rejected; it does not silently substitute newer source or claim that old GPU runs were repeated. Obtain vendor components according to [dependencies](DEPENDENCIES.md). Further work requires a correctly specified provider and kernel transport with ownership/lifetime and decoding verified; the observed stub alone does not provide either.
