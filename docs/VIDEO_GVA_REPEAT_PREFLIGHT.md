# Repeated video-session preflight: failed CPU control

A new laboratory host attempted three sequential H.264 decode requests in one
process, using the existing isolated video-observation chain. The **CPU
control did not qualify**: the first helper returned and produced six frames
matching 691,200 reference bytes; the second helper returned `nil`, so the
third request was not started. The host exited with code 10. These markers do
not establish that the second `VTDecompressionSessionCreate` was reached, or
why the second helper returned `nil`. No hardware-video repetition was run.

Independently, static inspection of the pinned dependency observer shows a
separate, definite obstacle: its interposed session-creation path uses
`begun.exchange(true)` to admit its first invocation; on a later invocation
it sets its profile pointer to null and returns `-50` instead of forwarding
the public create call. That one-shot guard must be redesigned and tested
before the observer can support a valid multi-session experiment. **It is not
proved to have caused the observed helper failure**; source-level tracing or
instrumentation is still needed to locate the earlier `nil` return.

The debugger reported target exit code 10; the target, debugger and launcher
were absent from the process table. The runner initially marked the shared
reservation unresolved because its original terminal parser expected exit
code 0. A separately locked reconciliation preserved the prior reservation
record and checked the actual exit and process absence before returning the
cooperative reservation to terminal. The debugger's own exit code was not
recorded and is not inferred. No process was killed. The CPU-only control is
not evidence of a GPU decode, and no system, driver or OCLP component changed.

The [sanitized audit](video-gva-repeat-one-shot-validation.json) pins the
source, failed host build, output frames and retained logs. The unsuccessful
builder and complete logs remain private laboratory artifacts; they are not
presented as a qualified reproduction path. Next, locate the `nil` return and
make a process-local, concurrency-safe repeatable observer with per-request
records; then requalify the software reference and negative controls before
any hardware-required test.
