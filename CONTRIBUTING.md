# Contributing

Keep NVIDIA driver modernization and Metal API extensions separate in issues and changes. State the layer affected: hardware, native compiler, user driver, resource/command runtime, or client application.

Contributions to original KeplerMetal code are accepted under the MIT license. Preserve upstream notices for modifications to external projects. Do not upload proprietary drivers, firmware, VBIOS, SDK headers, installers, disassemblies of entire vendor components, executable captures, credentials, or machine-specific configuration.

## Validation

1. Run `python3 tools/check_publication.py` and the portable tests.
2. Compile changed native sources on an appropriate macOS SDK. A build is not a GPU execution result.
3. For a GPU claim, report exact source and tool revisions, installed driver hash/version, dispatch evidence, output against an independent CPU oracle, and guards/negative controls.
4. Record PASS / FAIL / BLOCKED / NOT RUN distinctly. Expected broken controls must match their precise expectations; do not turn every nonzero exit into a pass.
5. Benchmark before claiming a gain. Separate prompt/compute work, command submission, waits, transfers, warm-up, and repeated trials as appropriate.

Private ABI and registry-ID checks deliberately fail closed. A new machine requires a separately reviewed profile and bounded qualification. Do not delete checks or replace pinned hashes merely to get past a rejection. The function/CAS repair is semantic and profile-specific, not an arbitrary register/offset substitution.

All experiments on the same GTX share **one host-wide reservation**, including native Metal probes. Preserve immutable executable copies, source/tool hashes, authoritative process termination, and the `lab_gpu_reservation.py` protocol. A timeout is not proof of termination. Never run simultaneous display-GPU cohorts accidentally.

System components remain read-only. Changes to installed drivers, OCLP, firmware, protections, clocks, or WindowServer are outside the current workflow. An adapted client is integration level 2; transparent support in ordinary applications is a separate level 3 goal.

Attach source patches and sanitized summaries. Keep raw binaries local and share their hashes plus regeneration commands. Hardware tests are opt-in and are not run by public CI.
