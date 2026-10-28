#!/usr/bin/env python3
"""Classify raw display/output frame visibility without game assets or Pillow.

Heuristics identify likely black/white frames, NOT graphical correctness.
Only basenames, dimensions and aggregate pixel statistics leave this program.
"""
import argparse
import json
import re
import sys
from pathlib import Path

CAPTURE = re.compile(r"^(display|output)_(\d+)_(\d+)x(\d+)_(rgba|bgra)\.raw$", re.I)
# RawChannelOrder in vk_presenter.cpp knows only RGBA/BGRA; HDR 'unknown'
# cannot be interpreted as an ordinary 8-bit, four-channel buffer.
MAX_PIXELS = 7680 * 4320
MAX_SAMPLES = 16384
DARK = 16
BRIGHT = 245
DOMINANT_RATIO = 0.985


def _region_stats(data, width, height, channel_order, region):
    x0, y0, x1, y1 = region
    count = (x1 - x0) * (y1 - y0)
    samples = min(count, MAX_SAMPLES)
    dark = bright = total = 0
    minimum, maximum = 255, 0
    for n in range(samples):
        offset = n * count // samples
        x = x0 + offset % (x1 - x0)
        y = y0 + offset // (x1 - x0)
        byte = 4 * (y * width + x)
        if channel_order == "bgra":
            b, g, r = data[byte], data[byte + 1], data[byte + 2]
        else:
            r, g, b = data[byte], data[byte + 1], data[byte + 2]
        # Approximate luma of the encoded 8-bit channels (not HDR luminance).
        level = (77 * r + 150 * g + 29 * b) >> 8
        dark += level <= DARK
        bright += level >= BRIGHT
        total += level
        minimum = min(minimum, level)
        maximum = max(maximum, level)
    return {
        "samples": samples,
        "mean_luma_0_255": round(total / samples, 2),
        "dark_ratio": round(dark / samples, 5),
        "bright_ratio": round(bright / samples, 5),
        "min_luma": minimum,
        "max_luma": maximum,
    }


def analyze_raw(path):
    """Validate exact pixel count and sample entire image + HUD-free center."""
    path = Path(path)
    match = CAPTURE.fullmatch(path.name)
    if not match:
        raise ValueError(f"unsupported raw capture filename: {path.name}")
    stage, index, w, h, order = match.groups()
    width, height = int(w), int(h)
    if width <= 0 or height <= 0 or width * height > MAX_PIXELS:
        raise ValueError(f"invalid capture dimensions: {path.name}")
    size = path.stat().st_size
    if size != width * height * 4:
        raise ValueError(f"truncated/oversized capture: {path.name} ({size} bytes)")
    # Byte read is bounded to 127 MiB by MAX_PIXELS; do not guess pixel layout.
    data = path.read_bytes()
    center = (width // 5, height // 5,
              max(width // 5 + 1, width - width // 5),
              max(height // 5 + 1, height - height // 5))
    # Sample the middle 60% separately: subtitles, letterboxes and HUD can
    # make a scene with black geometry appear to have visible pixels.
    all_stats = _region_stats(data, width, height, order.lower(), (0, 0, width, height))
    center_stats = _region_stats(data, width, height, order.lower(), center)
    if center_stats["dark_ratio"] >= DOMINANT_RATIO:
        visibility = "near_black"
    elif center_stats["bright_ratio"] >= DOMINANT_RATIO:
        visibility = "near_white"
    else:
        visibility = "varied_or_midrange"
    return {
        "file": path.name, "stage": stage.lower(), "frame": int(index),
        "width": width, "height": height, "channels": order.lower(),
        "visibility": visibility,
        "full_frame": all_stats, "center": center_stats,
    }


def _frame_assessment(display, output):
    if display is None or output is None:
        return "incomplete_pair"
    a, b = display["visibility"], output["visibility"]
    if a == "near_black" and b != "near_black":
        return "display_dark_output_not_dark"
    if a != "near_black" and b == "near_black":
        return "display_not_dark_output_dark"
    if a == b == "near_black":
        return "both_stages_dark"
    if a == b == "near_white":
        return "both_stages_bright"
    return "neither_stage_near_black"


def scan_folder(directory):
    """Never recurse into private saves/cache trees; capture files live here."""
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError("capture directory is missing or not a directory")
    collected, errors, unrecognized = {}, [], []
    for path in sorted(directory.glob("*.raw")):
        if not path.is_file():
            continue
        match = CAPTURE.fullmatch(path.name)
        if not match:
            unrecognized.append(path.name)
            continue
        try:
            frame = analyze_raw(path)
            key = (frame["frame"], frame["stage"])
            if key in collected:
                raise ValueError(f"duplicate frame/stage: {path.name}")
            collected[key] = frame
        except (OSError, ValueError) as error:
            errors.append(str(error))
    indices = sorted({key[0] for key in collected})
    frames = []
    for idx in indices:
        display, output = collected.get((idx, "display")), collected.get((idx, "output"))
        frames.append({
            "frame": idx, "display": display, "output": output,
            "assessment": _frame_assessment(display, output),
        })
    return {
        "frames": frames, "errors": errors, "unrecognized_raw": unrecognized,
        "note": ("Heuristic 8-bit center-luma inspection, not a rendering verdict. "
                 "Black cutscenes, masks, letterboxing and overlays may mislead. "
                 "HDR/unknown formats cannot be interpreted as RGBA/BGRA."),
    }


def compare_folders(baseline, candidate):
    """Only compare same-numbered complete frames; no claim of same scene."""
    old = {f["frame"]: f for f in baseline["frames"]}
    new = {f["frame"]: f for f in candidate["frames"]}
    results = []
    for idx in sorted(old.keys() & new.keys()):
        a, b = old[idx], new[idx]
        if any(a[s] is None or b[s] is None for s in ("display", "output")):
            state = "incomplete_pair"
        elif any((a[s]["width"], a[s]["height"]) !=
                 (b[s]["width"], b[s]["height"]) for s in ("display", "output")):
            state = "different_resolution"
        elif a["output"]["visibility"] != "near_black" and b["output"]["visibility"] == "near_black":
            state = "output_became_dark"
        elif a["display"]["visibility"] != "near_black" and b["display"]["visibility"] == "near_black":
            state = "display_became_dark"
        else:
            state = "no_dark_transition_detected"
        results.append({"frame": idx, "assessment": state,
                        "baseline": a["assessment"], "candidate": b["assessment"]})
    return {
        "matched": results,
        "baseline_only": sorted(old.keys() - new.keys()),
        "candidate_only": sorted(new.keys() - old.keys()),
        "note": ("Matching frame numbers/dimensions is not proof of the same scene. "
                 "For a release A/B, manually align checkpoint, camera, timing, "
                 "resolution, game/SKU, driver, GPU, settings and cache state."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture_dir", type=Path, help="Directory of display/output_*.raw")
    parser.add_argument("--baseline", type=Path, help="Older release capture directory")
    parser.add_argument("--output", type=Path, help="Write JSON report (otherwise stdout)")
    args = parser.parse_args(argv)
    try:
        current = scan_folder(args.capture_dir)
        baseline = scan_folder(args.baseline) if args.baseline else None
    except (ValueError, OSError) as error:
        print(f"Invalid capture input: {error}", file=sys.stderr)
        return 2
    report = {"schema_version": 1, "candidate": current}
    if baseline is not None:
        report["baseline"] = baseline
        report["comparison"] = compare_folders(baseline, current)
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    # Malformed raw inputs are never silently classified as good frames.
    return 2 if current["errors"] or (baseline and baseline["errors"]) else 0


if __name__ == "__main__":
    sys.exit(main())
