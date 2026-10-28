"""Ensure the real presenter does not request an unsafe raw image copy."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RawCaptureStructureTest(unittest.TestCase):
    def test_presenter_checks_actual_backing_format_before_allocating(self):
        src = (ROOT / "gpu/shadps4/video_core/renderer_vulkan"
               / "vk_presenter.cpp").read_text(encoding="utf-8")
        self.assertIn('RawCaptureChannelOrder(actual_format)', src)
        self.assertIn('if (!channel_order)', src)
        self.assertLess(src.index('if (!channel_order)'),
                        src.index('vmaCreateBuffer(instance.GetAllocator()'))
        self.assertIn('image.info.pixel_format);', src)
        self.assertNotIn('RawChannelOrder(view_info.format)', src)

    def test_test_target_in_full_native_runner(self):
        runner = (ROOT / "tools/run_tests.sh").read_text(encoding="utf-8")
        cmake = (ROOT / "gpu/CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('raw-capture-format)', runner)
        self.assertIn('add_executable(raw-capture-format-test', cmake)
        self.assertIn('tests/test_raw_capture_format.cpp', cmake)


if __name__ == "__main__":
    unittest.main()
