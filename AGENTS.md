# KeplerMetal working rules

- Read README.md, docs/BUILDING.md, docs/STATUS.md, and THIRD_PARTY_NOTICES.md.
- Modify project sources and local build/output directories only. No system driver, OCLP, firmware, protection, clock, or WindowServer changes.
- Never add proprietary binaries or local host/secrets configuration. Run tools/check_publication.py before committing.
- Native C API import and CAS implementations use MRC; other runtime objects use ARC. Preserve header ownership annotations.
- Keep private ABI/profile checks strict. Compilation, API detection, VRAM allocation, and actual GPU execution are distinct evidence.
- All GPU work uses the shared host reservation and immutable signed executables. No overlapping cohorts; observe terminal state before retrying.
- Historical builders may need omitted local fixtures. Do not invent archived results or silently repin them. Public source-only build: tools/build_from_source.py.
- Track branch A (driver behavior) separately from branch B (Metal extensions). Do not claim general Metal 3/4 support or performance without matching evidence.
