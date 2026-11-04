import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cairo

import collapsed_usage_view as dock
import collapsed_window_state as state_module
from usage_limit_view import widget_height
from usage_sources import UsageLimit


def render(used=0, dark=True, unknown=False):
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, dock.COLLAPSED_WIDTH, dock.COLLAPSED_HEIGHT)
    limits = [] if unknown else [UsageLimit('Codex', 'Codex', 'session', used)]
    dock.draw_collapsed_widget(cairo.Context(surface), limits, None, dark)
    surface.flush()
    return surface


def pixel(surface, x, y):
    offset = y * surface.get_stride() + x * 4
    return int.from_bytes(surface.get_data()[offset:offset + 4], sys.byteorder)


class CollapsedCapsuleTests(unittest.TestCase):
    def test_shape_and_gap_hit_testing_follow_the_visible_capsules(self):
        for provider, top in zip(dock.PROVIDERS, dock.CAPSULE_TOPS):
            self.assertEqual(dock.provider_at(0, top + dock.CAPSULE_HEIGHT / 2), provider)
            self.assertEqual(dock.provider_at(dock.COLLAPSED_WIDTH - 2, top + dock.CAPSULE_HEIGHT / 2), provider)
            self.assertIsNone(dock.provider_at(dock.COLLAPSED_WIDTH - 2, top + 1))
        self.assertIsNone(dock.provider_at(20, dock.CAPSULE_TOPS[0] + dock.CAPSULE_HEIGHT + 2))
        self.assertIsNone(dock.provider_at(-1, 30))

    def test_transparent_regions_pass_clicks_through_at_normal_and_double_scale(self):
        for scale in (1, 2):
            with self.subTest(scale=scale):
                region = dock.collapsed_input_region(dock.COLLAPSED_WIDTH * scale, dock.COLLAPSED_HEIGHT * scale)
                self.assertTrue(region.contains_point(10 * scale, 30 * scale))
                self.assertFalse(region.contains_point((dock.COLLAPSED_WIDTH - 1) * scale, 5 * scale))
                gap = dock.CAPSULE_TOPS[0] + dock.CAPSULE_HEIGHT + 2
                self.assertFalse(region.contains_point(10 * scale, gap * scale))

    def test_reference_material_is_black_with_gray_logo_backing_in_both_themes(self):
        top = dock.CAPSULE_TOPS[0]
        for dark in (False, True):
            with self.subTest(dark=dark):
                surface = render(dark=dark)
                self.assertEqual(pixel(surface, 1, top + 20), 0xFF000000)
                self.assertEqual(pixel(surface, dock.LOGO_CENTER_X, top + 13), 0xFFD3D3D3)
                self.assertEqual(pixel(surface, dock.COLLAPSED_WIDTH - 1, top), 0)
                self.assertEqual(pixel(surface, dock.BAR_X + 5, top + 20), 0xFF62D093)

    def test_quota_changes_only_the_bar_and_unknown_is_distinct_from_zero(self):
        full, empty, unknown = render(0), render(100), render(unknown=True)
        top = dock.CAPSULE_TOPS[0]
        for y in range(top + 4, top + dock.CAPSULE_HEIGHT - 4):
            for x in range(30, 90):
                self.assertEqual(pixel(full, x, y), pixel(empty, x, y))
        center_y = top + dock.CAPSULE_HEIGHT // 2
        self.assertNotEqual(pixel(empty, dock.BAR_X + 5, center_y), pixel(unknown, dock.BAR_X + 5, center_y))

    def test_left_edge_position_uses_the_chosen_monitor_and_clamps_vertically(self):
        monitors = [(-1920, 30, 1920, 1050), (0, 0, 2560, 1440)]
        self.assertEqual(dock.left_edge_position(-800, 2000, 240, 328, monitors),
                         (-1920, 1080 - dock.COLLAPSED_HEIGHT))
        self.assertEqual(dock.left_edge_position(500, 100, 240, 328, monitors), (0, 100))
        self.assertEqual(dock.left_edge_position(500, 2000, 240, 328, monitors),
                         (0, 1440 - dock.COLLAPSED_HEIGHT))
        self.assertEqual(dock.left_edge_position(12, 34, 96, 252, []), (12, 34))

    def test_accessibility_keeps_percentages_when_visual_text_is_hidden(self):
        description = dock.collapsed_accessible_label([UsageLimit('Claude Code', 'Claude Code', '5h', 20)])
        self.assertIn('Claude Code: 80% restante', description)
        self.assertIn('Codex: indisponível', description)

    def test_expanding_selects_the_provider_usage_view_and_restores_position(self):
        for available in (True, False):
            with self.subTest(available=available):
                limits = [UsageLimit('Claude Code', 'Claude Code', '5h', 20)] if available else []
                window = SimpleNamespace(
                    _all_limits=limits, _active_provider='Codex', _selected_limit=8,
                    _collapsed=True, _view_mode='overview', _widget_size=240,
                    _expanded_position=(350, 400), area=Mock(),
                    set_skip_taskbar_hint=Mock(), set_resizable=Mock(), set_size_request=Mock(),
                    resize=Mock(), move=Mock(), _sync_collapse_menu_label=Mock(),
                    _apply_window_layer=Mock(), _apply_input_region=Mock(), _ensure_visible=Mock(),
                    _save_position=Mock(),
                )
                with patch.object(state_module.GLib, 'idle_add'):
                    state_module.CollapsedWindowState._expand_from_provider(window, 'Claude Code')
                self.assertEqual(window._view_mode, 'usage')
                self.assertEqual(window._active_provider, 'Claude Code')
                self.assertEqual(window._limits, limits)
                self.assertEqual(window._selected_limit, 0)
                self.assertFalse(window._collapsed)
                window.move.assert_called_once_with(350, 400)
                window.resize.assert_called_once_with(240, widget_height(240, 'usage'))


if __name__ == '__main__':
    unittest.main()
