# Experimental typed vertex-buffer setter — not integrated

Status on 2026-10-27: **offline prototype and native pipeline construction only**.
No new draw or compute dispatch has been performed. The existing public
runtime does not implement this interface; do not dispatch this experimental
program or supply arbitrary context addresses.

The SDK-typed MSL in `bridge/src/air_vertex_binding.metal` emits
`air.set_vertex_buffer_render_command.p1i8` with an ordinary device pointer,
slot, fixed stride sentinel `-1`, and vertex-binding index. The experimental
translator preserves the shader's entry arithmetic and operation order while
rewriting the setter and existing typed triangle draw. Other primitives,
constant address space, dynamic stride and unrelated commands are refused.

A candidate owned context would retain the existing 32-byte root header and
add a 32-byte `KPVX` extension. Its inline rows contain the previous catalogue
identity, destination identity, exact buffer address, logical command slot and
binding index. A valid setter only changes the command's state identity; an
unmatched operation clears its record as a conservative laboratory refusal,
which is **not** a complete implementation of Metal's setter semantics.
Neither the candidate context nor a retained resource owner is implemented.
The prototype and `KPIX` indexed extension cannot yet be combined.

`air_vertex_transition.py` is an offline reference model, not a trusted device
address authority. It models transitions only when pipeline, fragment state,
index binding, geometry envelope and all other vertex bindings match. It
rejects ambiguous aliases, duplicate identities, unsupported spans and a table
larger than 64 rows. The future native implementation must build rows from
live, validated catalogue snapshots; retain and declare the actual buffers;
protect records/root against aliasing; preserve ordering and lifecycle; and
verify all rows before any GPU submission. Empty/reset state, null binding,
dynamic stride, pointer aliases and arbitrary catalogue combinations remain
unimplemented or deliberately rejected. A CPU model is not a runtime check.

The isolated iMac build extracted AIR SHA-256
`b8e67ce59ef9abeb0f75fe3871cfbe0968fbe36fe3515c7bbcad2c0d78a96380`
and normalized IR SHA-256
`1c7b8f1e1e1847f093b258adb83fdfe25bb86293b92fbac7334bef9be59e9ce0`.
The existing NVIDIA compiler constructed a pipeline for the translated shader;
its captured 2,432-byte program has SHA-256
`f8cc2d2f68617cc21590f13eb316923501772b1182e423a13db2fe879ee051eb`.
Offline decoding found no unresolved CALL. The constructor observer was
restored, the signed reservation reached terminal status, and the construction
host recorded zero command buffers and zero dispatches. This observation is
not evidence of correct hardware execution or a performance improvement.

With the same qualified SDK and an existing shared reservation directory:

```sh
python3 bridge/tools/public_air_vertex_binding.py build --out /absolute/new-build
python3 bridge/tools/public_air_vertex_binding.py inspect \
  --build /absolute/new-build --out /absolute/new-inspection \
  --reservation-root /absolute/common-lab/bridge
python3 bridge/tools/public_air_vertex_binding.py certify \
  --run /absolute/new-inspection --envydis /absolute/envytools/envydis
python3 -m unittest discover -s tests -p 'test_vertex_binding_offline.py' -v
```

Next acceptance gate: implement an owned, snapshot-checked context and safe
transition generation in the existing runtime; test the actual translated
program with independently checked output/images, no-setter and invalid-binding
controls, multiple slot and ordered-setter cases, native references and
non-regression, using the common GPU reservation. Only then consider this a
usable adapted-application feature. Native Apple ICB identity and transparent
application integration remain separate work.
