# A historical AMD `IOGVACodec` publication path

The [full update survey](VIDEO_GVA_ARCHIVE_SURVEY.md) found `IOGVACodec` in
the retained High Sierra `AMDRadeonX3000` binary, although its update plist did
not provide a matching key. A focused static analysis of its x86-64
`AMDGraphicsAccelerator::start` routine identifies this conditional path:

- At `0xcbe` and `0xcc4`, the code checks a byte in an associated structure and
  compares an accelerator field with `5`; failing either test skips the path.
- At `0xcd2` and `0xcd9`, it loads the strings `IOGVACodec` and `VCE`, then
  invokes the virtual slot at `0xce6` with those arguments.
- The accelerator vtable symbol is at `0x220a50`; the corresponding slot has
  an external relocation to `IORegistryEntry::setProperty(char const*, char
  const*)` at `0x220cd0`.

This supports a **static, conditional AMD property-publication path**. It does
not prove the runtime vtable target, which hardware satisfies the two tests,
or that the routine ran. `VCE` is an AMD value in this binary; it is **not** a
proven NVIDIA value and must not be used to claim GTX support. The result
shows why a plist-only absence cannot rule out code-created properties. The
full payload survey still finds no NVIDIA-labelled literal; a differently
encoded, indirect or external producer remains possible.

The private binary is the archive member with SHA-256
`0b288cd12e22f0ba40a241dbf42a6a00d779e1a028d670f73c1e487229711f86`.
The [audit](video-gva-amd-dynamic-property-validation.json) checks the survey,
code and string windows, symbol and vtable relocation, and four retained
REA/Ghidra 12.1.4 observations: string
`ev_b10f0527b93cd766fd36e523447f865bbafcf6baa6082d192b85547231e84a32`,
reference `ev_a4f49e7d46190b9e619c7a4263b9f56f23feec47a73105114bc82bd28327178a`,
containing procedure `ev_889ff8a572c35eeb0eb2be6b99d8b0e4a92a16b3c4aa766273ba125c9615b287`,
and function dossier `ev_a22bcc92ae3dfcfa641e48868f39172375b5b38984d3f544ac81b0302aede469`.
The independent `llvm-nm` and `llvm-objdump` checks identify the vtable and
relocation; the private binary and REA bundle are not published. No AMD or
NVIDIA driver code was executed, no GPU was used, and macOS/OCLP were not changed.

## Reproduction

Use the checked private payload described in [the survey](VIDEO_GVA_ARCHIVE_SURVEY.md).
Copy only the named member to a new private laboratory directory and verify the
hash above. The pinned audit also requires the retained private REA evidence bundle. To
repeat the analysis independently, run REA/Ghidra on that member, search for
`IOGVACodec`, inspect references to `0x110015`, resolve the containing
function and analyze `0x93e`. A newly exported bundle may have a different
digest and is not silently accepted as the retained bundle. Then run:

```sh
E=bridge/experiments/video_gva_archive_survey
python3 "$E/audit_amd.py" --binary /private/path/AMDRadeonX3000 \
  --survey /private/path/full-survey.json --rea /private/path/REA.private.json \
  --out /private/new-amd-audit.json
```

The code and vtable addresses are specific to this pinned binary. Investigating
a possible NVIDIA producer requires separately qualified evidence; neither an
AMD string nor a vtable patch is a decoder implementation.
