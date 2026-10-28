# Graphics regression checkpoint

## 2026-10-27: swapchain composite-alpha surface compatibility (draft)

The old `Swapchain::SetSurfaceProperties` selected `eOpaque` whenever
supported, otherwise **unconditionally `eInherit`**, even if the surface only
exposed `ePreMultiplied` or `ePostMultiplied`. Vulkan requires the selected
`VkSwapchainCreateInfoKHR::compositeAlpha` bit to be one of
`VkSurfaceCapabilitiesKHR::supportedCompositeAlpha`. Passing an unsupported
bit can cause validation errors, failed swapchain creation, or loss of
presentation on some window/driver configurations.

The renderer now chooses in preference order: Opaque, Inherit,
PreMultiplied, PostMultiplied, **only when advertised**. This preserves
its historical preference for Inherit whenever Opaque is absent. If none are supported it
reports an explicit assertion instead of sending an invalid bit to the driver.
The pure policy helper is tested for all four modes, combinations and an empty
capability mask without a GPU. It is part of the Windows native suite and a
lightweight Linux header-based check.

This addresses a real capability-negotiation defect. **The same unverified
Inherit fallback existed in windows-v0.6.1 and windows-v0.7.0**, so this
cannot independently explain the reported v0.6.1 → v0.7.x black-screen
regression. It has **not been established** as the cause of #10's Intel
fullscreen alt-tab error, #43/#47 black output or #68's stutters. GPU-backed
validation on affected hardware is still required.

## 2026-10-27: profile-gate the selective SSBO shader cache revisions (draft)

The prior #80/#81 revisions salted disk shader versions for every formatted
writable/writable SSBO even on hosts that never enable
`Profile::needs_ssbo_store_load_barrier`. That flag is currently enabled
for NVIDIA proprietary drivers, **not for AMD or Intel**. On the latter,
the serialized meta versions could reject reusable shaders despite generating
identical IR/SPIR-V, triggering avoidable shader translation/first-use stalls.

The cache metadata reader, warm-up path, pipeline-stage loader and shader-meta
writer now all receive the **same active device profile's gate** explicitly.
The salt is zero on profiles without this barrier requirement. On enabled
profiles it preserves the two additive salts: formatted writable (`1 << 18`)
and any writable buffer (`1 << 19`). The global shader binary format/layout
version stays unchanged. Standalone C++ tests cover all combinations and Python
source checks guard plumbing across save/reload/warm-up.

**One-time cache migration caveat:** AMD/Intel shader-meta blobs written under
the previous unconditional salt may be rejected and recompiled **once** because
their version changes back to unsalted; thereafter the new profile-appropriate
version is reusable. No user cache/saves are deleted or forcibly reset.
The effect on real frametimes requires matched cold/warm scene captures.


## 2026-10-27: atomic SSBO read-modify-write barrier coverage (draft)

The existing InsertSsboStoreLoadBarrier pass ignored `BufferAtomic*`
instructions even though they read and write the same resource. They now
participate in both read/write sets; barriers are added after atomics
only when there is a non-atomic load of the same binding, and after raw
stores when an atomic may read that binding. Two atomic-only operations do
not require extra barriers from this pass. This is restricted to
NVIDIA compatibility profiles that already enable this pass. Other GPUs
retain their behavior. Dependence analysis remains conservative by binding,
not a proof of access to an identical element.

Cached Shader::Info metadata marks atomics as written but does not distinguish
them from plain stores. A new additive per-shader binary salt (`1 << 19`)
recompiles all shaders with writable bindings as a safe conservative subset,
without invalidating read-only shader caches or deleting existing user data.
This can increase first-use compilation cost for writable shaders.

Focused real IR tests now cover atomic-to-load, store-to-atomic,
atomic-to-atomic, distinct bindings and profile-disabled behavior.
Windows CLANG64 build, full IR suite, hardware Vulkan validation and
matching reporter scene captures are still required. No fix for #43/#47
has been demonstrated.


## 2026-10-27: formatted SSBO store/load barrier coverage (PR pending)

Code review found that `InsertSsboStoreLoadBarrier` runs **before**
`LowerBufferFormatToRaw`, but its read/write opcode sets did not include
`LoadBufferFormatF32` or `StoreBufferFormatF32`. Consequently a shader with
a formatted store followed by a formatted or ordinary load on the same
resource binding could miss the device memory barrier that this
NVIDIA-specific compatibility pass is intended to add.

The patch adds those two opcodes to the existing classification **only**.
No barrier is added on hosts with
`Profile::needs_ssbo_store_load_barrier == false`. The pass still matches by
resource binding and conservatively inserts after stores when that binding
is loaded anywhere in the shader; this does **not** prove a same-address
dependence and may increase work on affected shaders.

Shader meta cache entries now use a selective per-shader binary version salt
(`1 << 18`) when the saved resource list contains a formatted and writable
binding. This avoids globally invalidating warmed SPIR-V for unaffected
shaders, but the affected subset still recompiles on first use. The salt is
independent of existing motion/float-atomic revisions and does not change the
base ShaderBinaryVersion. A dependency-free C++ test covers this predicate.

`tests/test_formatted_ssbo_barriers.cpp` runs the real IR pass on
formatted/ordinary store/load pairs and verifies exact barrier placement,
different bindings, disabled profiles, and existing conservative ordering.
The test must be built on Windows/MSYS2 CLANG64 with the rest of the GPU
suite; it does not prove Vulkan synchronization validation or #43/#47.
A matching hardware/capture retest remains mandatory.


## 2026-10-25: user retest of the local package

The user reports good gameplay with some remaining flicker. The corresponding
private log identifies the local RTX 5060 Laptop setup, but the profile's
capture and screenshot folders are empty. There is no chapter/checkpoint,
camera, draw ID, or image evidence to connect the flicker to the color/depth
change or another pass. Keep the visual issue open and do not add a broad
shader/layout workaround from this report alone.

## 2026-10-25: local color/depth overlap handling

The renderer now reports whether the color-to-depth overlap copy actually
completed. Unsupported copies no longer silently suppress the guest dispatch;
the overlap resolver retains the original color image and uses the valid depth
backing. A multisampled color-to-depth blit path was added with a cached pipeline
keyed by sample count and format.

`aliasing-test`, the full `tools/run_tests.sh` suite (48 C/C++ tests plus
Python), and isolated 130-second MSAA/no-MSAA smokes passed. Both smokes exited
0 without crash/hang and no reported VUIDs in captured logs; the MSAA capture
showed rendered prologue characters. Validation layers were not established as
active, so this is not a synchronization-validation pass. It does not validate
Chapter 5/8/9, the reporters' GPUs, or the public black-screen
issues. No release/package containing this local change has been tested by
reporters.

Current public evidence is negative for several v0.7.7 reports: #43 remains
black/white on an RTX 3060 Ti (CUSA00035 01.02), #47 has a black-screen report
on RX 6500 XT and an additional RX 560 report, #39 remains in Chapter 5 on RX
9070, #63 remains in Chapters 8/9 on RX 9070, #26 sun shadows remain absent,
and #36 lighting remains wrong on RX 6700 XT. Keep each symptom and hardware
separate; local smoke success is not a fix confirmation.

2026-10-22: preserve earlier correctness fixes while establishing measurement.

| Area | Evidence / remaining gate |
| --- | --- |
| Arena download / depth-store barriers | Existing regression tests preserved and passing |
| Visible pending graphics pipelines | Existing key-scoped waits preserved; warm sample records stalls rather than deleting the waits |
| Main-menu output on NVIDIA | Display capture in `out\checkpoint-20261022\captures` inspected |
| Combat, grenade particles, volumetrics, solar/cascade shadows | NOT TESTED in this checkpoint |
| AMD/Intel, wave32/wave64, LDS divergence | NOT TESTED; do not change shader semantics on menu evidence |
| Z-fighting, vertex explosions, black polygons | No new scene-specific fix or visual-correctness claim |

The prior RCA in `PROGRESS.md` distinguishes confirmed synchronization hazards
from gated shader hypotheses. Keep that distinction. Validation-layer absence in
a normal run is not a synchronization-validation pass.

Need a reproducible gameplay checkpoint, matching camera/input replay, before/after
captures, resource/draw IDs and vendor-specific hardware evidence before accepting
additional graphics fixes. Do not blanket-clear caches or disable effects.

## 2026-10-22 release investigation

Reviewed the screenshot in #45 (washed-out character and crushed surroundings on
an RTX 4080 Laptop), the attached runtime logs in #36 (RX 6700 XT) and #63
(RX 9070, Chapters 8/9), and retained `out\vsm` / `out\htile2` comparisons.
The logs contain HTILE-read markers, but no Vulkan validation or synchronization
hazard identifying the bad lighting pass. Absence of those messages is not a
validation pass. The older comparisons show depth/debug views or transitional
frames, not matching camera checkpoints for these reports.

No new lighting/shadow default is changed in v0.7.7. In particular, do not replace
the reported issue with a gamma/exposure workaround, force all shadow tiles
nonempty, or enable every experimental lighting flag. The release does include
previously merged preservation of shader-written HTILE, custom-border-color
sampler cache keys, resolved descriptors after texture rebind, and per-target
additive blending. These are reasons to request a retest, not proof that #26,
#36, #39, #45 or #63 is resolved.

The remaining gate is a chapter/checkpoint plus repeatable camera/input and
before/after final-output captures on the reporting GPU. Include `user\last_run.log`,
driver version, output resolution, upscaler and graphics settings. Existing
`THEORDER_LIGHTING_TEST` tokens (`shading`, `msdepth`, `dref`, `bias`) are diagnostic
only: test one token at a time against an unchanged baseline, preserving saves
and caches. Shader-changing tokens use distinct cache versions. A menu/prologue
smoke test cannot validate the Chapter 5/8/9 defects.
