# Metal queue failure after experimental video association

**Qualification result: FAIL for the tested post-association Metal-queue scenario.** Although the experimental video lease previously opened, associated and closed both connections with zero return codes, this follow-up shows that those return codes do not establish that an ordinary Metal device remains usable afterward.

The same signed own-process test uses a pinned legacy AppleGVA caller and selected GTX `nvAccelerator`. A retained Metal device has the same registry ID. Each measurement builds the same Metal compute pipeline and tries to create a new command queue before and after the tested lifecycle. The gate still replaces the NVIDIA create-stub with a local return-14 witness; the Sierra provider is not invoked. The earlier process-local policy/dependency substitutions remain.

| Sequence | Runs | New queue before | New queue afterward |
| --- | ---: | --- | --- |
| No video context, no dispatch | 2 | success | success |
| Type-3 context opened and closed, no shared client | 2 | success | success |
| Type-3 context plus type-6 shared connection, associated and closed; no dispatch | 2 | success | **nil** |
| Same association and close, with a GPU dispatch before close | 2 | success | **nil** |
| No video context, GPU dispatches before and after | 1 | success | success |

The four associated cases report successful open, association and close statuses, yet `newCommandQueue` returns nil after both connections close. Library, function and pipeline creation still succeed in those recorded after phases. No buffer or command is created after the nil queue. The control without a GPU dispatch excludes GPU work as a necessary trigger in these scenarios. The context-only control does **not** distinguish the separate effects of opening a type-6 client, associating it, and closing either connection. This is a bounded observation, not a claim that a specific driver instruction is faulty or that all Metal applications are affected.

In the two associated GPU runs, the pre-close command buffer completes and its 4,096 output words per run match an independent CPU oracle. The no-context GPU control completes both phases, for **16,384 exact GPU-written words total**. Six no-dispatch processes preserve **40,960 sentinel words** across their captured phases; all 448 recorded guard words match. The association cases produce no post-close capture because queue creation fails. Nine signed terminal processes are nonoverlapping. Hardware-required VideoToolbox creation still returns `-12913` and produces zero images in every case. No video-engine work, performance improvement or installed-driver fix is established.

The [audit](video-provider-compute-validation.json) checks frozen sources, inputs, signed receipts, reservation intervals, route choices, phase outcomes and raw word captures. Its status `EXPECTED_FAILURE_CONFIRMED` means the regression was reliably detected, **not** that the product scenario passed. Sixteen portable provider-auditor tests pass, including rejection of altered output and incorrect classification of this failure. An earlier exploratory build showed the same missing after capture but lacked stage diagnostics; it remains in the lab and is excluded from these counts.

The Metal device stays alive throughout the local test; the shared connection is a newly opened test client, not demonstrated to be Metal's own client. Driver/framework internals and WindowServer are not exhaustively observed. This result does not prove that system-wide state is damaged or persists beyond the process. No system driver, framework, OCLP or firmware was modified.

## Consequence and next step

Do not use the experimental associated lease in an application that needs continued Metal operation on the basis of successful close statuses alone. Isolate type-6 open/close from association and examine the lifetime/ownership of the shared client and retained Metal resources before proposing a fix. Do not forward an unqualified video selector or substitute a fabricated successful reply.

## Re-audit the exact cohort

Use the retained private lab and exact boot-specific driver profile. No vendor binary or raw capture is distributed; a changed build or profile needs independent requalification.

```sh
R="$HOME/Documents/ChatGPT/Metal 4/nvidia-880m-lab/bridge/results"
EXP=bridge/experiments/video_provider_compute
python3 "$EXP/audit.py" --build "$R/video-provider-compute-build-20261028-02" \
 --out "$R/video-provider-compute-reaudit-new.json" \
 --hosts "$R/video-provider-compute-nocontext-skip-20261028-01" "$R/video-provider-compute-attach-skip-20261028-01" \
 "$R/video-provider-compute-context-skip-20261028-01" "$R/video-provider-compute-attach-skip-20261028-02" \
 "$R/video-provider-compute-nocontext-skip-20261028-02" "$R/video-provider-compute-attach-gpu-20261028-02" \
 "$R/video-provider-compute-context-skip-20261028-02" "$R/video-provider-compute-nocontext-gpu-20261028-01" \
 "$R/video-provider-compute-attach-gpu-20261028-03"
python3 -m unittest discover -s tests -p 'test_video_provider_*.py' -v
```
