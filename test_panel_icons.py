import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from panel_icons import render_status, status_icon


def pixels(surface, x_start, x_end):
    surface.flush()
    data = surface.get_data()
    return [int.from_bytes(data[y * surface.get_stride() + x * 4:y * surface.get_stride() + x * 4 + 4], sys.byteorder)
            for y in range(surface.get_height()) for x in range(x_start, x_end)]


class PanelIconTests(unittest.TestCase):
    def test_text_changes_color_at_the_widget_status_thresholds(self):
        for remaining, expected in ((60, 0x62D093), (59, 0xFFB340), (30, 0xFFB340), (29, 0xFF5F65), (None, 0xB3BAC7)):
            with self.subTest(remaining=remaining):
                surface = render_status("codex", "88%", remaining)
                pixel = max(pixels(surface, 24, surface.get_width()), key=lambda value: value >> 24)
                alpha = pixel >> 24
                self.assertGreater(alpha, 200)
                # Font antialiasing stores premultiplied RGB in the transparent image.
                for shift in (16, 8, 0):
                    actual = ((pixel >> shift) & 255) * 255 / alpha
                    self.assertAlmostEqual(actual, (expected >> shift) & 255, delta=2)

    def test_quota_changes_only_the_text_preserving_the_logo(self):
        for key in ("codex", "gemini", "claude", "argon", "claude-code"):
            healthy = render_status(key, "88%", 88)
            depleted = render_status(key, "0%", 0)
            self.assertEqual(pixels(healthy, 0, 18), pixels(depleted, 0, 18))
            self.assertTrue(any(pixel >> 24 for pixel in pixels(healthy, 0, 18)))

    def test_no_ring_or_track_around_the_logo(self):
        surface = render_status("codex", "88%", 88)
        self.assertTrue(all(pixel == 0 for pixel in pixels(surface, 18, 23)))
        data = pixels(surface, 0, 18)
        self.assertTrue(all(pixel == 0 for pixel in data[:18] + data[-18:]))

    def test_badges_fit_panel_height_and_unchanged_images_are_cached(self):
        with TemporaryDirectory() as directory:
            for key in ("codex", "gemini", "claude", "argon", "claude-code"):
                surface = render_status(key, "100%", 100)
                self.assertEqual(surface.get_height(), 20)
                self.assertGreater(surface.get_width(), surface.get_height() * 1.5)
                path = status_icon(key, "100%", 100, Path(directory))
                modified = path.stat().st_mtime_ns
                self.assertEqual(status_icon(key, "100%", 100, Path(directory)).stat().st_mtime_ns, modified)


if __name__ == "__main__":
    unittest.main()
