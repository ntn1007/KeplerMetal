# Native video transport inside the test process

The native decoder service callback now runs through a public anonymous XPC
listener inside the disposable Intel test process. Four software cases produce
24 exact H.264 images through that transport. Including external-service
controls and the constructor observer, 48 images / 5,529,600 active NV12 bytes
match the existing independent FFmpeg CPU references. This establishes a
bounded native transport experiment, with explicit application integration.

Hardware-required creation still returns `-12906` with zero images. The final
local presence experiment observes two selections of the H.264 GVA candidate,
one `FigRegistryItemGetFactory` entry and an actual load of **AppleGVA 10.0.20**,
UUID `ca5414f369373c059ea2d82b35afd4f0`. The factory's actual returned value and
the complete refusal cause remain unobserved. A missing AppleGVA image is no
longer an adequate explanation for this particular experiment.

[Scalar results, hashes and qualification failures](video-local-service-validation.json).

## Contract and scope

The shipped Intel `VTDecoderXPCService` entry passes
`VTRemoteDecodeServer_XPCServiceConnectionHandler` to public `xpc_main`.
Retained REA/Ghidra entry evidence
`ev_63ad658ae6dc86220b197dcba7812bbaa15f9db653fa28ec035b18101a832b1a`
and the SDK26.2 callback type establish the connection-handler slot's ABI.
They do not establish the entire native service's initialization and lifetime
contract. The implementation checks the loaded VideoToolbox version, UUID,
callback offset, executable extent and SHA-256 before calling it on a real
accepted connection. No arbitrary private protocol message is constructed.

The constructor replacement applies only to the exact native caller at
VideoToolbox offset6326308 and the decoder service name. It returns a retained,
inactive endpoint client with the requested target queue; native VideoToolbox
sets its handler and activates it. The server callback sets its original event
handler and resumes its accepted peer. Native VideoToolbox generates and
processes all codec messages. Bounded observations copy only opcode/status
scalars and public peer PIDs. The native service and other processes are not
modified. The replacement constructor result is deliberately different, and
the report records that fact.

The first two observed native messages, `uber` and `Strt`, return0/0 for software
and0/-12906 for the completed local hardware case. The public peer PID equals
the test PID. This is execution of the native server callback in our process;
it does not certify an installed service replacement or hardware decoding.
The native initializer sets up its own SIGTERM handling in this child. The
outer shared host lease, immutable signed executable and inner12second watchdog
remain in use. No watchdog timeout or requested SIGKILL occurred in this cohort.

Apple documents [anonymous-listener testing](https://developer.apple.com/documentation/technotes/tn3113-testing-xpc-code-with-an-anonymous-listener)
and [application-private XPC helpers](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingXPCServices.html).
Those public mechanisms do not guarantee this private decoder implementation's
behavior. An independently initialized helper process remains a possible later
experiment, not an implemented result here.

## Final artifact and controls

The final laboratory build is `video-owned-service-build-20261018-04`. It
preserves the qualified decoder/catalog/entry objects and dependency library.
It builds the new transport and a metadata observer with capacity512. Its
seven fresh processes are terminal, exit0, nonoverlapping and used no kill.

| Request | Route / dependency choice | Owned callback | Images | Result |
| --- | --- | ---: | ---: | --- |
| Inspect | Native | 0 | 0 | Resident preflight only |
| Software | Native | 0 | 6 | Exact CPU reference |
| Software | Owned | 1 | 6 | Exact CPU reference; native replies0/0 |
| Hardware required | Owned / native | 0 | 0 | -12906 before transport |
| Hardware required | Owned / wrong key | 0 | 0 | -12906 before transport |
| Hardware required | Native / present key | 0 | 0 | -12906; original external service |
| Hardware required | Owned / present key | 1 | 0 | Native replies0/-12906; complete local capture |

The existing dependency experiment substitutes one original NULL `IOGVACodec`
query result with a retained Boolean, restricted by the byte-pinned caller,
GTX registry ID4294968458, IOService plane, recursive option1 and original
hardware requirement. It changes no registry entry. The frozen dependency
source actually uses an atomic process-wide hardware scope during a single
public create; an earlier handoff described it as thread-local incorrectly.
This milestone does not broaden that scope or rebuild that library. Native
software controls observe no local queries; the owned software cases observe
two, with no substitution. Only one substitution is observed in the hardware
presence case; no additional server query is invented.

## Preserved failures

Across this milestone, all33 signed hosts are terminal and nonoverlapping.
Four failed qualifications remain explicit:

- Public XPC V1: a pre-reply client PID was unknown. The pending request was
  correctly canceled, but the identity test failed.
- Public XPC V2: the server invalidation event was absent. The peer block could
  capture a reference into a destroyed listener block. V3 captures a weak_ptr
  value and assigns the peer's serial queue explicitly; its six controls pass.
- Native transport V2: an owned hardware presence case crashed during native
  client connection cleanup. Our code retained and explicitly canceled a client
  owned by VideoToolbox. V3 removes that extra client ownership and cancellation.
  The failed process and its crash receipt remain preserved. One changed run
  supports that diagnosis; a general native lifetime repair is not established.
- Native transport V3: the hardware create returned-12906 and the native
  transport completed, but269 metadata observations exceeded capacity256.
  Thirteen were dropped and the original host correctly returned6. This was a
  capture-capacity failure, not a watchdog timeout. V4 uses capacity512 and
  captures all269 with zero drops.

The 12 public-XPC hosts include10 passes and2 failures. Their independent Python
oracle rechecks43,792 copied uint32 words,3 primer words and4 pending-request
cancellations. These CPU controls perform no native video or GPU computation.
Seven original-source version patches reconstruct14 archived source views;
none contains Apple/NVIDIA code. No historical evidence was rewritten.

## Reproduction with existing local prerequisites

These are late laboratory builders; the prerequisite binary/fixture directories
are intentionally absent from the public source release. Use your separately
obtained installation and locally regenerated prerequisites, as described in
[BUILDING.md](BUILDING.md) and [DEPENDENCIES.md](DEPENDENCIES.md). Exact native
profiles are required; do not repin them merely to bypass a refusal.

From the laboratory `bridge/` directory, use fresh output names:

```sh
python3 tools/native_video_local_xpc.py build \
  --runtime-build results/video-peer-build-20261018 \
  --out results/repro-public-xpc-build
python3 tools/native_video_local_xpc.py run \
  --build results/repro-public-xpc-build --mode cancel --seed 0x13579 \
  --out results/repro-public-xpc-cancel --reservation-root .

python3 tools/native_video_routing.py build \
  --dependency-build results/video-dependency-build-20261018-02 \
  --profile results/video-peer-build-20261018/assets/routing-profile.json \
  --out results/repro-constructors-build
python3 tools/native_video_routing.py run \
  --build results/repro-constructors-build --mode inspect --codec H264 \
  --out results/repro-constructors-inspect --reservation-root .

python3 tools/native_video_local_service.py build \
  --routing-build results/repro-constructors-build \
  --out results/repro-owned-service-build
python3 tools/native_video_local_service.py run \
  --build results/repro-owned-service-build --mode inspect --route native \
  --out results/repro-owned-inspect --reservation-root .
python3 tools/native_video_local_service.py run \
  --build results/repro-owned-service-build --mode cpu --route owned \
  --out results/repro-owned-cpu --reservation-root .
python3 tools/native_video_local_service.py run \
  --build results/repro-owned-service-build --mode hardware --route owned \
  --override present-key --out results/repro-owned-hw-presence --reservation-root .
```

Wait for the exact manifest and authoritative process state after each run.
The final command's observed result is a refused hardware create with0images;
it must not be reported as hardware decoding. The complete archived cohort
also includes sync/async at both seeds and the native/wrong-key controls above.
Do not replay a nonterminal process or flatten every nonzero exit to success.

The independent historical auditors expect the dated, immutable directories
named in their source. They recheck files and never launch native programs:

```sh
python3 tools/audit_video_local_xpc.py --lab-root .. --out results/public-xpc-audit-new.json
python3 tools/audit_video_local_service.py --lab-root .. --out results/owned-video-audit-new.json
```

## Next driver investigation

The subsequent [factory/policy experiment](VIDEO_FACTORY_POLICY.md) establishes
the loader return and a second eligibility gate. It also explicitly records the
nonzero FinF/Inva replies retained by the software transport; full service
lifetime remains unqualified. The paragraph below records this milestone's
original next step.

The newly observed AppleGVA factory path is the next useful boundary. Establish
its exact factory return and loaded implementation before attributing the
refusal to policy, an absent legacy backend, the NVIDIA VA stubs, or hardware.
Read the pinned CoreMedia factory loader and AppleGVA image first. No new
private factory call, older framework load, driver installation or service
replacement has been performed here.

The 83 protected files, AppleVA policy, OCLP,36 common runtime sources and
common runtime archive remain unchanged. Full Metal suites and a new M1 run
were NOT RUN; no benchmark or speedup is claimed. BranchA gains a usable local
native diagnosis path. BranchB gains no new Metal feature in this milestone.
