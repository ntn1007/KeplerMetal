# Reproducibility and provenance

`SOURCE_SNAPSHOT.json` maps each exported file to its original lab-relative path and SHA-256, its public SHA-256, size and publication-edit flag. Runtime sources are unchanged. Four script files received local path or interpreter-default changes; private host transfer scripts are excluded. The FP64 hash-only include was recovered from the frozen SDK source, not an executable.

The export includes **source and metadata**, not the laboratory's 24 GiB of downloads/builds/captures. It preserves the code needed to study the algorithms and verification procedures, but does not claim every late archival command works immediately after cloning. Many scripts have explicit prerequisites from earlier experiments and intentionally pin their bytes.

The standalone public build compiles all runtime objects without those binary prerequisites. Its link-check has no GPU calls. The portable tests cover publication policy, original-source hash preservation and archive extraction boundaries; they do not attest the old GPU results.

Regenerating a carrier/metallib with a different SDK may produce a different hash or private ABI. Preserve the mismatch, investigate it, and qualify a new profile. Do not silently edit a pin to accept new bytes. A new build or compiler result never inherits GPU qualification solely through matching source text.

For new reports record: source commit, working-tree state, compiler/SDK versions, upstream commits and patches, exact inputs/binaries and hashes, driver/device identity, fresh run directories, CPU oracle/guards, negative-control expectations, process termination, and separate PASS/FAIL/BLOCKED/NOT RUN states. Include command and phase logs locally; redact private host data before sharing.

Public source checks and CPU builds are distinct from numerical GPU validation. No original binary evidence archive is included or presented as a fresh public run.
