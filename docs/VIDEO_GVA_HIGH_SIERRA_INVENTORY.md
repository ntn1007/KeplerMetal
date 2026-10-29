# Historical Apple NVIDIA codec-property inventory

The retained macOS 10.13.6 Combo update payload contains **15 GeForce/NVDA
extension plists and 19 selected executable members** in the inspected
paths. None of those plists contains the key `IOGVACodec`; none of the selected
executables contains its literal bytes in ASCII, UTF-16LE or UTF-16BE. This
includes `GeForce.kext`, `NVDAGK100Hal.kext`, `NVDAResman.kext` and
`GeForceVADriver.bundle`.

The absence is deliberately bounded: this update is not an inventory of every
file in a complete High Sierra installation. A property could be generated
dynamically, encoded differently, supplied by another component, or inherited
through another registry path. No NVIDIA codec string or compatible GTX 880M
runtime has been identified. These observations do not prove that the GPU
lacks a video engine or that a producer cannot exist.

As positive controls from the **same archive**, the scanner finds string
values in six Intel graphics plists and one AMD graphics plist. Their values
are not NVIDIA configuration. The scanner reads the whole 5,801,167,872-byte
uncompressed cpio stream, checks its SHA-256 and trailer, parses selected
plists recursively and inspects bounded binary members without extracting or
executing them. The [audit receipt](video-gva-high-sierra-inventory-validation.json)
records selected member hashes and the exact search scope. A first exploratory
scan omitted a 51,517,744-byte Tesla binary because of its 40 MiB limit; the
qualified audit raises the explicit bound to 64 MiB and includes it.

The retained archive is linked to the Apple-signed update and earlier bundle
checks in [VIDEO_HIGH_SIERRA_COMPARISON.md](VIDEO_HIGH_SIERRA_COMPARISON.md).
The current audit verifies the cpio hash; it does not repeat the original disk
image and package-signature checks. It performs no GPU or vendor execution and
modifies no macOS, NVIDIA or OCLP component.

## Reproduction

Use the privately retained, already extracted High Sierra payload described in
the earlier comparison. The audit reads roughly 5.4 GiB and requires a fresh
output path; it refuses an archive of a different size, digest or inventory.
It does not redistribute Apple binaries.

```bash
CPIO='/path/to/high-sierra-10.13.6/extract/high-sierra-payload.cpio'
OUT='/path/to/nvidia-880m-lab/bridge/results/gva-historical-inventory-new.json'
python3 bridge/experiments/video_gva_historical_inventory/audit.py --archive "$CPIO" --out "$OUT"
python3 -m unittest discover -s tests -p 'test_video_gva_historical_inventory.py'
```
