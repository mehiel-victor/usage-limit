"""Counters reflect received quotas, including zero, instead of assumed subscriptions."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cairo

import usage_limit_panel as panel
import usage_limit_view as view
import usage_limit_widget as widget
from panel_model import GROUPS
from usage_sources import UsageLimit


class AvailableQuotaTests(unittest.TestCase):
    def window(self, collapsed=False):
        return SimpleNamespace(_all_limits=[], _active_provider='Claude Code', _selected_limit=2,
                               _collapsed=collapsed, area=Mock(), _provider_menu_item=Mock(),
                               _apply_collapsed_geometry=Mock(), get_position=Mock(return_value=(0, 800)),
                               get_size=Mock(return_value=(66, 172)), _expand_from_provider=Mock(),
                               _refresh_generation=1)

    def test_disappearing_selected_provider_selects_an_available_one(self):
        window = self.window()
        limits = [UsageLimit('Codex', 'Codex', 'session', 100)]
        widget.UsageLimitWidget._render_limits(window, limits)
        self.assertEqual(window._active_provider, 'Codex')
        self.assertEqual(window._limits, limits)
        self.assertEqual(window._selected_limit, 0)
        window._provider_menu_item.set_visible.assert_called_once_with(False)

    def test_refresh_recomputes_collapsed_geometry_when_providers_change(self):
        window = self.window(collapsed=True)
        widget.UsageLimitWidget._render_limits(window, [UsageLimit('Codex', 'Codex', 'session', 20)])
        window._apply_collapsed_geometry.assert_called_once_with((0, 800), (66, 172))

    def test_total_failure_exits_collapsed_mode_instead_of_leaving_an_invisible_dock(self):
        window = self.window(collapsed=True)
        widget.UsageLimitWidget._finish_refresh(window, 1, [], True)
        self.assertTrue(window._error)
        self.assertEqual(window._all_limits, [])
        window._expand_from_provider.assert_called_once_with('Codex')

    def test_expanded_selector_has_no_unavailable_provider_or_phantom_click_target(self):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 240, 360)
        for providers, labels in (({'Codex', 'Antigravity'}, ['C', 'A']), ({'Claude Code'}, []), (set(), [])):
            with self.subTest(providers=providers), patch.object(view, '_draw_text') as draw_text:
                view._draw_controls(cairo.Context(surface), True, False, None,
                                    view.theme_colors(True), 'Codex', providers)
                self.assertEqual([call.args[1] for call in draw_text.call_args_list], labels)
        self.assertIsNone(view.control_at(*view.PROVIDER_TOGGLE, provider_count=1))
        self.assertIsNone(view.control_at(view.PROVIDER_TOGGLE[0] + 38, view.PROVIDER_TOGGLE[1], provider_count=2))

    def test_panel_hides_unavailable_groups_and_keeps_zero_quota_visible(self):
        indicators = {group.key: Mock() for group in GROUPS}
        controller = SimpleNamespace(indicators=indicators, refresh_items=[], add_detail=Mock(),
                                     add_action=Mock(return_value=Mock()), refresh=Mock(), quit=Mock())
        with patch.object(panel.Gtk, 'Menu'), patch.object(panel.Gtk, 'SeparatorMenuItem'), \
             patch.object(panel, 'status_icon', return_value=Path('/synthetic/badge.png')), \
             patch.object(panel, 'configured_profiles', return_value=[{'name': 'test', 'home': ''}]):
            limits = [UsageLimit('Codex', 'Codex', 'session', 100),
                      UsageLimit('Antigravity', 'Claude and GPT', 'weekly', 20)]
            panel.UsagePanel.render(controller, limits, set())
            active, passive = panel.AyatanaAppIndicator3.IndicatorStatus.ACTIVE, panel.AyatanaAppIndicator3.IndicatorStatus.PASSIVE
            indicators['codex'].set_status.assert_called_with(active)
            indicators['claude'].set_status.assert_called_with(active)
            indicators['claude-code'].set_status.assert_called_with(passive)
            indicators['gemini'].set_status.assert_called_with(passive)
            panel.UsagePanel.render(controller, [], {'Codex', 'Antigravity'})
            for indicator in indicators.values():
                indicator.set_status.assert_called_with(passive)

    def test_panel_starts_passive_until_a_quota_response_arrives(self):
        created = []
        def indicator(*_args):
            result = Mock()
            created.append(result)
            return result
        controller = SimpleNamespace(indicators={}, hold=Mock(), refresh=Mock(), refresh_items=[],
                                     add_detail=Mock(), add_action=Mock(), quit=Mock())
        controller.render = lambda *args, **kwargs: panel.UsagePanel.render(controller, *args, **kwargs)
        with patch.object(panel.AyatanaAppIndicator3.Indicator, 'new', side_effect=indicator), \
             patch.object(panel, 'status_icon', return_value=Path('/synthetic/badge.png')), \
             patch.object(panel.GLib, 'timeout_add_seconds', return_value=1):
            panel.UsagePanel.do_activate(controller)
        self.assertEqual(len(created), len(GROUPS))
        for item in created:
            item.set_status.assert_called_once_with(panel.AyatanaAppIndicator3.IndicatorStatus.PASSIVE)


if __name__ == '__main__':
    unittest.main()
