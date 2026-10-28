# Raw frame visibility diagnosis: black/white scene versus composition

The port records **two stages of the same VideoOut flip** when frame dumping
is enabled in `vk_presenter.cpp`:

- `display_NNN_<width>x<height>_rgba.raw` (or `_bgra.raw`):
  the guest display-buffer image **before** the FSR/post-processing path.
  This file may be absent when the temporal upscaler overrides the display.
- `output_NNN_<width>x<height>_rgba.raw` (or `_bgra.raw`):
  the presenter's final image **before** blitting to the swapchain. This is
  not a screenshot of the actual monitor. HDR/unknown channel orders cannot
  be treated as eight-bit RGBA/BGRA captures.

These two stages are particularly useful for #43 and #47, where reporters
hear music/dialogue and can see UI but the scene is black. The difference
between *display dark* and *output dark* suggests different places to
instrument next; it does **not** by itself prove a shader or presentation bug.

## Capture a matched scene

Use a new **empty** folder for each build to avoid overwriting older captures
(the dumper reuses frame numbers from zero after a restart). Preserve existing
profiles, shader caches, saves and installed builds. Launch the process with
`THEORDER_DUMP_DIR` pointing to that folder and
`THEORDER_FRAME_DUMP_TRIGGER` to a unique trigger-file path. The variables
must be present **when the game process starts**. At the exact same saved
checkpoint/camera on v0.6.1 and the candidate build, create the trigger file
once to capture one flip; the game removes that file after observing it.

For example, after setting the capture variables in the same PowerShell
process that launches the port:

```powershell
$env:THEORDER_DUMP_DIR = "D:\triage\v061"
$env:THEORDER_FRAME_DUMP_TRIGGER = "D:\triage\trigger-v061.flag"
# Start your existing launcher from this PowerShell and load the checkpoint.
# Once the scene is visible (or the failure reproduces), execute:
New-Item -Path $env:THEORDER_FRAME_DUMP_TRIGGER -ItemType File -Force
```

Use different `D:\triage\v07x` and trigger paths for the newer release.
Do **not** set a high `THEORDER_FRAME_DUMP_INTERVAL` for prolonged play:
raw 1080p frames can consume tens of MiB per flip. In a bright/black-screen
case, additionally save a screenshot and a redacted `user/last_run.log`.

Run with Python 3.10+ (no Pillow, no GPU or game files required):

```powershell
python tools/black_screen_triage.py D:\triage\v07x --baseline D:\triage\v061 --output D:\triage\visibility.json
```

The report records frame numbers, dimensions, channel order, 8-bit luma
statistics and **the filenames only**, not absolute capture paths or player
details. Review any log separately before sharing. Corrupt/truncated captures
are reported and cause a nonzero CLI exit; unknown HDR or other raw formats
are listed as unrecognized and not silently classified.

## How to interpret the results

| Stage assessment | What it suggests, not proves |
| --- | --- |
| `display_dark_output_not_dark` | The display buffer was almost entirely dark but post-processing/overlay added visible pixels; investigate guest render targets, shader images and descriptors |
| `display_not_dark_output_dark` | The display buffer had visible pixels but presenter output became dark; inspect FSR, post-processing, composition and output layouts |
| `both_stages_dark` | Could be a dark cutscene, intentionally black frame, or a problem before composition; inspect synchronized checkpoint and logs |
| `incomplete_pair` | No reliable stage attribution (temporal override, capture failure or unsupported pixel format) |
| `output_became_dark` in release comparison | Candidate output is near-black where baseline was not, **only meaningful when the same checkpoint/time/settings are established externally** |
| `different_resolution` | Do not compare these captures as the same render target |

The heuristic samples whole-frame and center 60% separately with pixel
thresholds; it may be fooled by letterboxing, flash frames, subtitles,
near-black scenes, HDR, different output formats and timing differences.
It does not decode Vulkan GPU commands, identify a bad shader hash or
prove gameplay correctness. A matching real GPU/driver capture and reporter
retest are still mandatory. Never close #43/#47 merely because this report
generates an assessment.

Historical source diff of the v0.6.1→v0.7.0 transition:
`b333700d`, `7b67a84f`, `2e2b9e39`, `8bdf10d8`. The same
swapchain composite-alpha fallback existed on both sides; it is not by itself
an explanation for that particular regression.
