# Scoped synthetic AppleGVA codec-property counterfactual

Two separate, instrumented H.264 requests returned the synthetic ASCII string
`KeplerMetalProbe` for one previously absent `IOGVACodec` property query. At
the pinned property-return breakpoint the result was non-null and the observed
node byte was still zero. At two subsequent list stops, the matching head
address had flags `1,0,0,1`, versus `1,0,0,0` with the probe off. The
observed field after enumeration was nevertheless zero and each hardware-required
VideoToolbox session returned `-12913` and zero images.

This narrows one hypothesis: **making this property non-null with this synthetic
string does not by itself make the tested route enumerate a decoder**. It does
not establish which branch executed, why enumeration remained empty, or whether
an actual NVIDIA codec string would change the outcome. A matching address is
not proof of allocation lifetime or object identity. The debugger can perturb
timing; the experiment retains earlier process-local VideoToolbox presence and
board counterfactuals. No hardware video execution or performance gain was
established.

A subsequent [static filter analysis](VIDEO_GVA_RENDERER_FILTER.md) identifies a separate numeric classification that would exclude the observed field if the entry and control flow remain unchanged. The branch itself remains untraced.

The value is fabricated for the experiment. It is not an NVIDIA configuration
value, a claimed supported codec, or a driver fix. The observer is confined to
its own process and only substitutes a retained `CFString` for an originally
null result when the pinned AppleGVA callsite, key, class, registry identifier,
options and explicit synthetic mode all match. Two negative controls force the
key or registry-ID predicate false inside the observer; they are **simulated
predicate mismatches**, not queries against another actual key or device. Both
refused substitution and produced the same `-12913` and zero images as the
probe-off control. A standalone predicate test checked one accepted case and
nine refusals; a CPU CoreFoundation control checked type, retention, ASCII
conversion and preservation of a non-null original. A software VideoToolbox
control produced six frames matching 691,200 reference bytes.

The [audit receipt](video-gva-codec-counterfactual-validation.json) binds the
six terminal runs, their logs and frozen inputs. All cooperative reservations
finished and the target and debugger were reported absent. This reservation
coordinates participating lab runners; it does not claim exclusive GPU access
against other software. No system driver, framework, OCLP or firmware was
modified.

## Reproduction on the retained iMac profile

Run from the repository root. The private pre-existing lab builds and test
fixtures are required; they are not published. The base and marker builders
refuse mismatched hashes or system profiles. Use fresh output paths and run the
GPU-related commands sequentially; if a target or debugger has an unknown
outcome, preserve the reservation and investigate before retrying. Different
machines and builds require a separately qualified profile, not a repin.

```bash
LAB='/path/to/nvidia-880m-lab/bridge'
R="$LAB/results"
E=bridge/experiments/video_gva_codec_probe
B="$R/codec-probe-base-new/base"
M="$R/codec-probe-marker-new"
python3 "$E/build.py" --lab "$LAB" --base "$R/gva-property-build-20261028-01" --out "$R/codec-probe-base-new"
python3 bridge/experiments/video_gva_property_link_witness/build_gva.py --lab "$LAB" --base "$B" --calibration "$R/lldb-property-link-calibration-20261029-01" --reserved-control "$R/lldb-property-link-reserved-cpu-20261029-01" --out "$M"
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$M" --out "$R/codec-cpu-new" --mode cpu --witness on --probe off
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$M" --out "$R/codec-wrong-key-new" --mode current --witness on --probe wrong-key
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$M" --out "$R/codec-wrong-id-new" --mode current --witness on --probe wrong-id
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$M" --out "$R/codec-off-new" --mode current --witness on --probe off
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$M" --out "$R/codec-synthetic1-new" --mode current --witness on --probe synthetic
python3 "$E/run_gva.py" --lab "$LAB" --base "$B" --build "$M" --out "$R/codec-synthetic2-new" --mode current --witness on --probe synthetic
python3 "$E/audit.py" --base "$B" --original-base "$R/gva-property-build-20261028-01" --build "$M" --runs "$R/codec-cpu-new" "$R/codec-wrong-key-new" "$R/codec-wrong-id-new" "$R/codec-off-new" "$R/codec-synthetic1-new" "$R/codec-synthetic2-new" --out "$R/codec-audit-new.json"
```
