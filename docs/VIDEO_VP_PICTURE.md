# CPU model of H.264 VP picture parameters

The experimental [VP picture model](../bridge/experiments/video_bsp_staging/VideoPicture.h)
constructs the 756-byte block produced by selected Mesa 26.2.4 Nouveau VP3
helpers. It includes caller-supplied scaling matrices, order counts, reference
entries, reference field flags and a target slot. It also returns a **proposed**
target-state transition. Logical identities are caller-supplied values, not
GPU addresses. Invalid dimensions, field ranges or reference identities are
refused without changing the output.

This is a CPU-only model, not a decoder. It does not parse or validate complete
H.264 pictures, allocate or retain actual surfaces, maintain a decoded-picture
buffer, submit commands or establish completion. In particular, the proposed
state must not be applied merely because preparation succeeded. The returned
`0x1113` value mirrors the Mesa helper; it is not a macOS capability claim.
The input structures can describe synthetic combinations that are not legal
H.264 streams. The model must not be used to submit video work to the GTX.

## Evidence and reproduction

The [validator](../bridge/experiments/video_bsp_staging/validate_video_picture.py)
checks a pinned Mesa archive and exact source members, compiles the two original
VP helper functions and their layout helpers into a local CPU reference, and
compares all 756 bytes and the target-state proposal across 4,096 deterministic
synthetic cases. Refusal checks include mismatched identities, invalid fields
and out-of-range slots. The reference uses a minimal synthetic decoder wrapper;
this is not the complete Mesa driver or proof of its behavior on macOS.
[iMac receipt](video-vp-picture-validation.json).

The same source and locally generated reference are transferred with hash
verification and run under ASan/UBSan on the ARM MacBook.
[MacBook receipt](video-vp-picture-mac-validation.json). These checks do not
execute NVIDIA video engines or qualify a private NVIDIA interface.

```sh
E=bridge/experiments/video_bsp_staging
python3 "$E/validate_video_picture.py" --archive /path/to/mesa-26.2.4.tar.xz \
  --tree /path/to/mesa-26.2.4 --out /path/to/new-local-result
python3 "$E/validate_video_picture_mac.py" --baseline /path/to/new-local-result \
  --out /path/to/new-mac-result --host SSH_ALIAS --remote-dir /path/to/new/remote-result
```

Further work needs complete picture metadata and reference lifetime handling,
a validated macOS video transport and actual decoded frames independently
compared with a CPU reference. None of those is supplied by this model.
