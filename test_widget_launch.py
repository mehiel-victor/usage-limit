import unittest
from unittest.mock import Mock, patch

import usage_limit_widget as widget_module


class WidgetLaunchTests(unittest.TestCase):
    def test_reopening_reuses_and_restores_the_existing_window(self):
        window = Mock(_collapsed=False)
        application = Mock()
        application.get_windows.return_value = [window]
        with patch.object(widget_module, "UsageLimitWidget") as constructor:
            widget_module.activate_widget(application)
        constructor.assert_not_called()
        window.show_all.assert_called_once()
        window.deiconify.assert_called_once()
        window._ensure_visible.assert_called_once()
        window.present.assert_called_once()

    def test_opening_a_collapsed_window_expands_the_selected_provider(self):
        window = Mock(_collapsed=True, _active_provider="Antigravity")
        application = Mock()
        application.get_windows.return_value = [window]
        widget_module.activate_widget(application)
        window._expand_from_provider.assert_called_once_with("Antigravity")
        window.present.assert_called_once()

    def test_first_launch_creates_and_presents_one_window(self):
        application = Mock()
        application.get_windows.return_value = []
        window = Mock(_collapsed=False)
        with patch.object(widget_module, "UsageLimitWidget", return_value=window) as constructor:
            widget_module.activate_widget(application)
        constructor.assert_called_once_with(application)
        window.show_all.assert_called_once()
        window.present.assert_called_once()

    def test_missing_cairo_bridge_fails_with_an_actionable_message(self):
        with patch.object(widget_module.gi, "require_foreign", side_effect=ImportError), \
             patch.object(widget_module.Gtk, "Application") as constructor:
            with self.assertRaisesRegex(SystemExit, "instale python3-gi-cairo"):
                widget_module.main()
        constructor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
