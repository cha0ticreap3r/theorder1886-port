"""Black-screen display/output diagnosis: synthetic pixels, no GPU or Pillow."""
import json
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from paths import ROOT
sys.path.insert(0, str(ROOT / 'tools'))
import black_screen_triage as triage  # noqa: E402


def write_raw(directory, stage, index, width, height, rgb, order='rgba'):
    path = Path(directory) / f'{stage}_{index:03d}_{width}x{height}_{order}.raw'
    r, g, b = rgb
    pixel = bytes((r, g, b, 255) if order == 'rgba' else (b, g, r, 255))
    path.write_bytes(pixel * (width * height))
    return path


class BlackScreenTriageTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.old = self.root / 'old'
        self.new = self.root / 'new'
        self.old.mkdir()
        self.new.mkdir()

    def test_stage_diagnosis_with_black_display_and_visible_overlay(self):
        write_raw(self.new, 'display', 0, 12, 10, (0, 0, 0))
        write_raw(self.new, 'output', 0, 12, 10, (10, 150, 200), 'bgra')
        item = triage.scan_folder(self.new)['frames'][0]
        self.assertEqual(item['assessment'], 'display_dark_output_not_dark')
        self.assertEqual(item['display']['visibility'], 'near_black')
        self.assertEqual(item['output']['visibility'], 'varied_or_midrange')
        self.assertGreater(item['output']['center']['mean_luma_0_255'], 70)

    def test_post_processing_black_output_from_visible_display(self):
        write_raw(self.new, 'display', 7, 8, 8, (60, 110, 140))
        write_raw(self.new, 'output', 7, 8, 8, (0, 0, 0))
        item = triage.scan_folder(self.new)['frames'][0]
        self.assertEqual(item['assessment'], 'display_not_dark_output_dark')
        self.assertEqual(item['output']['visibility'], 'near_black')

    def test_solid_white_is_distinct_from_black_and_hud(self):
        white = write_raw(self.new, 'output', 1, 6, 6, (255, 255, 255), 'bgra')
        result = triage.analyze_raw(white)
        self.assertEqual(result['visibility'], 'near_white')
        self.assertEqual(result['center']['bright_ratio'], 1.0)
        self.assertEqual(triage.scan_folder(self.new)['frames'][0]['assessment'],
                         'incomplete_pair')

    def test_center_roi_ignores_letterbox_black_bars(self):
        img = self.new / 'display_002_10x10_rgba.raw'
        pixels = bytearray()
        for y in range(10):
            for x in range(10):
                pixels.extend((120, 150, 140, 255) if 2 <= x < 8 and 2 <= y < 8
                              else (0, 0, 0, 255))
        img.write_bytes(pixels)
        result = triage.analyze_raw(img)
        self.assertEqual(result['visibility'], 'varied_or_midrange')
        self.assertGreater(result['full_frame']['dark_ratio'], 0.5)
        self.assertEqual(result['center']['dark_ratio'], 0.0)

    def test_exact_length_and_channel_order_are_required(self):
        path = self.new / 'display_000_5x5_rgba.raw'
        path.write_bytes(b'\x00' * 99)  # Expected 100 bytes.
        found = triage.scan_folder(self.new)
        self.assertEqual(found['frames'], [])
        self.assertEqual(len(found['errors']), 1)
        self.assertIn('truncated/oversized', found['errors'][0])
        (self.new / 'output_000_5x5_unknown.raw').write_bytes(b'\x00' * 100)
        self.assertEqual(len(triage.scan_folder(self.new)['unrecognized_raw']), 1)

    def test_release_comparison_explicitly_flags_noncomparable_frames(self):
        for stage in ('display', 'output'):
            write_raw(self.old, stage, 0, 8, 8, (120, 130, 140))
            write_raw(self.new, stage, 0, 8, 8, (0, 0, 0))
        result = triage.compare_folders(triage.scan_folder(self.old),
                                        triage.scan_folder(self.new))
        self.assertEqual(result['matched'][0]['assessment'], 'output_became_dark')
        self.assertIn('not proof of the same scene', result['note'])
        # Different output dimensions must not be treated as comparable
        (self.new / 'output_000_8x8_rgba.raw').unlink()
        write_raw(self.new, 'output', 0, 9, 8, (0, 0, 0))
        result = triage.compare_folders(triage.scan_folder(self.old),
                                        triage.scan_folder(self.new))
        self.assertEqual(result['matched'][0]['assessment'], 'different_resolution')

    def test_report_does_not_disclose_absolute_paths_and_cli_fails_on_corrupt(self):
        secret_dir = self.root / 'private-user-profile'
        secret_dir.mkdir()
        write_raw(secret_dir, 'display', 17, 4, 4, (0, 0, 0))
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'tools' / 'black_screen_triage.py'),
             str(secret_dir)], capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertNotIn(str(self.root), proc.stdout)
        self.assertNotIn('private-user-profile', proc.stdout)
        self.assertEqual(data['schema_version'], 1)
        self.assertEqual(data['candidate']['frames'][0]['frame'], 17)
        with (secret_dir / 'display_017_4x4_rgba.raw').open('ab') as output:
            output.write(b'\x00')
        error = subprocess.run(
            [sys.executable, str(ROOT / 'tools' / 'black_screen_triage.py'),
             str(secret_dir)], capture_output=True, text=True)
        self.assertEqual(error.returncode, 2)
        self.assertIn('truncated/oversized capture', error.stdout)


if __name__ == '__main__':
    unittest.main()
