# RAW capture format safety

The `THEORDER_FRAME_DUMP_TRIGGER` diagnostic in
`gpu/shadps4/video_core/renderer_vulkan/vk_presenter.cpp` previously
reserved **width × height × 4 bytes** and issued `vkCmdCopyImageToBuffer`
even when the Vulkan image format was not known to have that byte size.
For example, R16G16B16A16 float takes 8 bytes per pixel and
R32G32B32A32 float takes 16 bytes per pixel, which the original buffer
cannot safely hold. The old file suffix `_unknown.raw` also provided
no trustworthy channel interpretation.

The renderer now uses the **backing image's actual format** for the
`display` capture and checks `RawCaptureChannelOrder` **before creating
the buffer or submitting the transfer**. Only known 8-bit RGBA/BGRA
UNORM/sRGB images are captured. HDR, floating-point, depth and other
unknown formats are logged as skipped and will not be mislabeled as
ordinary four-byte captures. When capture is disabled, the normal
rendering path remains unchanged.

The pure C++ test `tests/test_raw_capture_format.cpp` verifies all
supported channel layouts and rejects HDR/float/depth formats.
`tests/test_raw_capture_structure.py` verifies the guard's placement
and use of backing format in the real presenter. These run in the
dedicated Linux check and the full Windows test suite.

This is **diagnostic memory safety**, not a proven fix for black output.
Use `docs/RAW_FRAME_VISIBILITY_TRIAGE.md` after PR #96 is available
to compare display/output frames safely. If one stage is unavailable
due to HDR or an upscaler, the result is inconclusive; never infer
render correctness from a missing capture. Never delete player saves,
existing caches or older captures to run this diagnostic.
