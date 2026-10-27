# Video context identity and mapped address coverage

This experiment correlates two previously separate observations in the same
process: the registry identity of an owned `nvVideoContext`, and the coverage
of its two fence-related mapped virtual addresses. It does not implement
hardware video decoding or establish destruction of kernel mapping objects.

Two fresh, signed processes independently selected the GTX through the NVIDIA
`10de:1198` PCI ancestor and retained its Metal device. Each opened the video
context and shared client, then associated them. Before opening, the eventual
context registry ID was absent; after opening and after association, exactly
one new entry with that ID reported the witness process as its creator. The
mapping test was gated on this observation and on valid bounded iterators.

Each process then called `IOConnectMapMemory` for types 2 and 1, once each.
Both calls returned disjoint, 4,096-byte regions. The process did not read or
write their contents. Each address was covered by a Mach VM region before
closing the video context; immediately afterward neither address was covered,
and the observed registry ID was absent. Both remained absent after closing
the shared client. The calls to close returned zero. The two processes had
distinct PIDs and distinct observed context IDs.

The [offline audit](video-owner-map-validation.json) rechecks five serialized
host processes: inventory, wrong target, association-only control and two
observations. It checks frozen source and executable hashes, terminal leases,
iterator validity, creator matching, the sizes and coverage observations,
and that the host does not directly import `IOConnectUnmapMemory`,
`IOConnectCall*` or `mach_vm_deallocate`. Four separate anonymous-memory
controls check the coverage method and adjacent pages. An executable import
check does not trace indirect work inside frameworks or the driver; the
cooperative reservation does not exclude WindowServer.

Absence of a virtual region at the sampled address does not establish the
identity or destruction of `IOMemoryMap`, descriptor references or channel
objects, and address reuse can confound later samples. The creator property
correlates the registry node with a process but does not establish a unique
connection-port-to-node identity. An earlier explicit unmap attempt returned
`0xe00002c2` for both types and remains a **failed cleanup test**. It was not
repeated in this cohort and is not fixed by closing the context. The mapped
contents, private video selectors and GPU video commands were not tested.

## Reproduction on the qualified profile

`LAB` is the existing laboratory containing `results/` and the cooperative
reservation; `RID` is the current `nvAccelerator` registry ID. Choose fresh
output paths and do not overlap other laboratory GPU tests:

```sh
python3 bridge/tools/video_context_owner_map.py build --out "$LAB/results/owner-map-build-new"
python3 bridge/tools/video_context_owner_map.py run --build "$LAB/results/owner-map-build-new" --out "$LAB/results/owner-map-inventory-new" --reservation-root "$LAB" --mode inventory
python3 bridge/tools/video_context_owner_map.py run --build "$LAB/results/owner-map-build-new" --out "$LAB/results/owner-map-wrong-new" --reservation-root "$LAB" --mode wrong-target
python3 bridge/tools/video_context_owner_map.py run --build "$LAB/results/owner-map-build-new" --out "$LAB/results/owner-map-attach-new" --reservation-root "$LAB" --mode attach --registry-id "$RID"
python3 bridge/tools/video_context_owner_map.py run --build "$LAB/results/owner-map-build-new" --out "$LAB/results/owner-map-first-new" --reservation-root "$LAB" --mode owner-map-close --registry-id "$RID"
python3 bridge/tools/video_context_owner_map.py run --build "$LAB/results/owner-map-build-new" --out "$LAB/results/owner-map-second-new" --reservation-root "$LAB" --mode owner-map-close --registry-id "$RID"
mkdir "$LAB/results/owner-map-vm-build-new"
cp bridge/tools/vm_region_control.c "$LAB/results/owner-map-vm-build-new/source.c"
xcrun clang -arch x86_64 -O2 "$LAB/results/owner-map-vm-build-new/source.c" -o "$LAB/results/owner-map-vm-build-new/vm-control"
codesign --force --sign - "$LAB/results/owner-map-vm-build-new/vm-control"
python3 bridge/tools/run_vm_region_control.py "$LAB/results/owner-map-vm-build-new" "$LAB/results/owner-map-vm-control-new"
python3 bridge/tools/audit_video_context_owner_map.py \
  --inventory "$LAB/results/owner-map-inventory-new" --wrong "$LAB/results/owner-map-wrong-new" \
  --attach "$LAB/results/owner-map-attach-new" --first "$LAB/results/owner-map-first-new" --second "$LAB/results/owner-map-second-new" \
  --vm-control "$LAB/results/owner-map-vm-control-new/result.json" --vm-source "$LAB/results/owner-map-vm-build-new/source.c" --vm-binary "$LAB/results/owner-map-vm-build-new/vm-control"
python3 -m unittest discover -s tests -p test_video_owner_map_audit.py -v
```

The profile checker pins local driver files, loaded kext UUIDs and the kernel
UUID; it does not compare running kernel bytes. No driver, framework, OCLP or
firmware is changed. Further video work still needs a qualified channel,
resource ownership, synchronization and a real decoded-image comparison.
