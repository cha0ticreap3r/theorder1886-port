# v0.6.1 → v0.7.0 black-scene regression: controlled bisect

## Evidence available on 2026-10-28

Issues [#43](https://github.com/mateussmeneses/theorder1886-port/issues/43)
and [#47](https://github.com/mateussmeneses/theorder1886-port/issues/47)
report working audio and UI/subtitles while world geometry is black or
white, with some reporters explicitly identifying **v0.6.1 as working**
and **v0.7.0+ as affected** on their own hardware. Other issues describe
flicker, green/blue artifacts, lag and missing shadows; those are not
necessarily the same defect.

The GitHub commit comparison is exactly four commits (36 changed files):

| First-parent order | Commit | Changes relevant to this investigation |
| --- | --- | --- |
| Baseline | `windows-v0.6.1` | Reported working scene on some affected machines; not a perfect visual reference |
| 1 | `b333700d797139e69b1ea3af73c9d4e6fbc33439` | GCN 16-bit/addr64 translation, NVIDIA-only SSBO barrier, fallback image format handling, tile rules, runtime image-layout locking and texture checks |
| 2 | `7b67a84fc2ccdb7aae27b04a152c905849b6aa78` | Deferred texture uploads, buffer-cache memoization, rasterizer changes, draw recording synchronization, and language/DLC/game patch changes |
| 3 | `2e2b9e397cd817f36478b71c18c6756a480ac526` | Reverted experimental render-target clearing and related texture-cache changes; removed forced SKU behavior |
| 4 | `8bdf10d8fc4e9a5a07117206930668ff2012f760` | Reverted aggressive texture rejection and buffer obtain memoization; removed broken engine patches |
| Candidate | `windows-v0.7.0` | End of this four-commit series |

**Do not assume the regression must come from step 4**, because steps
3 and 4 were repairs and some earlier implementation remains. Later
versions have additional changes and cannot directly identify which of
these first four introduced a specific black scene. The `compositeAlpha`
fallback was present in both v0.6.1 and v0.7.0, and therefore does
not independently explain the version-specific regression.

## Decision-oriented testing procedure

1. Reproduce with **the exact same game SKU/update/eboot hash**,
   output settings and GPU/driver. Record fullscreen/borderless, HDR,
   VSync, engine frame rate, upscaler and MSAA. Do not change a driver
   between A/B builds. Avoid unrelated background apps.
2. Use copies of the same save and **separate user/cache directories**
   for each build. Never run an old build against a newer build's
   writable save folder. Do not delete original saves, caches or
   captured screenshots.
3. For the same checkpoint/camera/scene time, record one dump from both
   stages with `THEORDER_FRAME_DUMP_TRIGGER` and a unique
   `THEORDER_DUMP_DIR`. Use
   `python tools/black_screen_triage.py <candidate_dir> --baseline <old_dir>`
   as a *heuristic*, not an image correctness test.
4. First verify the v0.6.1 and v0.7.0 endpoints on the same machine.
   Only then test the **four historical commits in sequence** in a
   *separate, reproducible build environment* with matching dependencies.
   Mark each as scene visible, scene black/white, crash or indeterminate.
   Do not call a broken or unreproducible build a rendering regression.
5. The earliest reproducible transition from visible to black/white is
   the next change set to bisect into individual graphics paths.
   Request GPU/driver and the redacted runtime log from each state.
6. If the output is dark but the display stage is not, inspect FSR,
   post-processing and composition. If the display stage is dark while
   output contains overlays, inspect guest render targets,
   texture descriptors and shader specialization. If either dump is
   absent or is HDR/unknown format, record **indeterminate**, not
   fabricated pixel values.
7. Repeat a warm-cache visit for stutters, and report raw frame-time
   percentiles separately from cold compilation. Use
   `tools/batch_runs.py` / `tools/regression_report.py` with isolated
   profiles for longer runs; track build SHA and hash of game data.

**Limits:** Hosted GitHub Actions compiles/tests the port but has no
actual graphics device. It cannot determine whether any intermediate
commit renders the affected scene correctly. A matched real hardware
capture is required before changing shader/texture behavior or closing
#43/#47/#63/#68.

## Minimal report template for a tester

```text
GPU + driver:
CPU + Windows version:
Game SKU/update + eboot SHA-256:
Port tag/commit:
Checkpoint and exact camera:
Resolution / aspect / HDR / upscaler / FPS:
First visit cold cache: visible / dark / bright / crash
Second visit warm cache: visible / dark / bright / crash
Frame dump stage: display present? output present? format names?
Black-screen triage assessment:
Redacted last_run.log path or issue attachment:
```

Keep copyrighted game assets, actual saves, full memory dumps, local
filesystem paths and other personal information out of public issues.
