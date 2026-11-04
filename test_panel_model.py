import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from install_panel import install_entries
from panel_model import GROUPS, group_label, group_limits, remaining_percent
from usage_sources import UsageLimit


class PanelModelTests(unittest.TestCase):
    def test_labels_show_only_available_quota_without_service_names(self):
        for group in GROUPS:
            self.assertEqual(group_label(group, [UsageLimit("Codex", "Codex", "session", 12)]), "88%")
            self.assertEqual(group_label(group, []), "—")

    def test_separates_argon_and_shared_claude_quota_from_gemini(self):
        limits = [UsageLimit("Codex", "Codex", "session", 11),
                  UsageLimit("Antigravity", "Gemini Models", "weekly", 22),
                  UsageLimit("Antigravity", "Gemini Models", "5h", 0),
                  UsageLimit("Antigravity", "Claude and GPT models", "weekly", 65),
                  UsageLimit("Antigravity", "Claude and GPT models", "5h", 0),
                  UsageLimit("Antigravity", "Gemini 4 Argon", "weekly", 43)]
        groups = group_limits(limits)
        self.assertEqual({key: remaining_percent(items) for key, items in groups.items()},
                         {"codex": 89, "gemini": 78, "claude": 35, "argon": 57, "claude-code": None})

    def test_unknown_quota_is_not_reported_as_full_or_empty(self):
        self.assertIsNone(remaining_percent([]))

    def test_unknown_groups_are_not_assigned_to_gemini(self):
        groups = group_limits([UsageLimit("Antigravity", "Other models", "weekly", 40)])
        self.assertTrue(all(not items for items in groups.values()))

    def test_uses_most_restrictive_window_and_all_profiles(self):
        groups = group_limits([UsageLimit("Codex", "Work", "session", 15),
                               UsageLimit("Codex", "Personal", "weekly", 80)])
        self.assertEqual(remaining_percent(groups["codex"]), 20)


class PanelInstallerTests(unittest.TestCase):
    def test_installs_login_and_menu_entries_idempotently(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            targets = install_entries(root / "data", root / "config")
            times = [path.stat().st_mtime_ns for path in targets]
            install_entries(root / "data", root / "config")
            self.assertEqual(times, [path.stat().st_mtime_ns for path in targets])
            self.assertIn("X-GNOME-Autostart-enabled=true", targets[1].read_text())

    def test_preserves_modified_autostart_before_changing_other_entries(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            targets = install_entries(root / "data", root / "config")
            targets[1].write_text("user preference")
            targets[0].unlink()
            with self.assertRaises(ValueError):
                install_entries(root / "data", root / "config")
            self.assertFalse(targets[0].exists())
            self.assertEqual(targets[1].read_text(), "user preference")


if __name__ == "__main__":
    unittest.main()
