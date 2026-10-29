# Repeated session diagnostic: metadata observer refuses the second begin

Two fresh-process **CPU** diagnostic runs each attempted repeated H.264
requests. An instrumented version of the original wrapper reported
`KPRegistryMetadataBegin` succeeding for request 1 and returning false for
request 2. The wrapper then returned `nil` before calling the underlying
decoder. In each run request 1 produced six frames matching 691,200 reference
bytes, the second result was `nil`, and request 3 did not start. Both debugger
and target exited normally under the cooperative lab reservation.

The instrumented wrapper differs from its pinned original only by logging
the Boolean return before the original false-return check. The diagnostic
host records the `nil` and stops rather than exiting with code 10. Static
inspection of the pinned metadata observer source shows that a successful
begin sets an atomic `configured` flag and subsequent begins refuse it. The
source and compiled library are bound to the retained build inputs. Thus the
metadata observer explains the refusal **in these diagnostic runs** and is a
strong candidate for the earlier failed preflight; that earlier process had
no per-call metadata marker, so its exact return site was not directly seen.

There is a second independent single-use guard in the dependency observer,
which would still prevent forwarding a subsequent session creation if the
metadata guard were addressed. Neither observer has been made repeatable yet.
A safe change must give each session separate evidence, handle concurrent calls
and prove restoration/cleanup, then pass CPU and failure controls before a
hardware-required experiment.

No repeated hardware decode or NVIDIA video-engine execution is demonstrated.
No driver, OCLP or system component was modified. The
[sanitized audit](video-gva-repeat-metadata-validation.json) binds code and
receipts; debugger instrumentation can affect execution.

## Reproduction

Requires the prior private, pinned laboratory inputs and the cooperative GPU
reservation. Use fresh paths. Run only after confirming all earlier sessions
are terminal; if a child outcome is unknown, retain the reservation.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_repeat_sessions
B="$R/gva-property-build-20261028-01"
W="$R/gva-cache-hw-build-20261029-01"
BUILD="$R/repeat-diagnostic-build-new"
python3 "$E/build.py" --lab "$LAB" --base "$B" --witness-build "$W" --out "$BUILD"
python3 bridge/experiments/video_gva_cache_witness/run_gva.py --lab "$LAB" --base "$B" --build "$BUILD" --out "$R/repeat-diagnostic-cpu-1-new" --mode cpu --witness on
python3 bridge/experiments/video_gva_cache_witness/run_gva.py --lab "$LAB" --base "$B" --build "$BUILD" --out "$R/repeat-diagnostic-cpu-2-new" --mode cpu --witness on
python3 "$E/audit_metadata.py" --base "$B" --build "$BUILD" --metadata-build "$R/video-registry-metadata-build-20261016" --owned-build "$R/video-owned-service-build-20261018-04" --runs "$R/repeat-diagnostic-cpu-1-new" "$R/repeat-diagnostic-cpu-2-new" --out "$R/repeat-metadata-audit-new.json"
```
