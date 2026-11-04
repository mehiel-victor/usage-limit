"""Offline contract tests: https://code.claude.com/docs/en/statusline#available-data."""
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import cairo

import collapsed_usage_view as dock
from panel_model import group_limits, remaining_percent
import usage_limit_panel as panel
import usage_limit_widget as widget
from usage_limit_view import control_at, draw_widget, PROVIDER_TOGGLE
import usage_sources as sources

ROOT = Path(__file__).resolve().parent
NOW = 2_000_000_000


def payload():
    # Synthetic values, using the official field names and Unix-second contract.
    return {"rate_limits": {
        "five_hour": {"used_percentage": 23.5, "resets_at": NOW + 1800},
        "seven_day": {"used_percentage": 41.2, "resets_at": NOW + 86400},
    }}


class ClaudeParserTests(unittest.TestCase):
    def test_subscription_windows_use_the_official_contract(self):
        result = sources.parse_claude_limits(payload())
        self.assertEqual([(item.provider, item.window, item.remaining_percent, item.resets_at)
                          for item in result],
                         [("Claude Code", "5h", 76, NOW + 1800),
                          ("Claude Code", "7 dias", 59, NOW + 86400)])

    def test_each_window_is_optional_and_gateway_overage_is_clamped(self):
        result = sources.parse_claude_limits({"rate_limits": {
            "spend_limit": {"used_percentage": 114.5, "resets_at": NOW + 3600,
                            "used_usd": 300, "limit_usd": 250},
        }})
        self.assertEqual([(item.window, item.remaining_percent) for item in result], [("gasto", 0)])

    def test_missing_windows_are_unknown_instead_of_full_quota(self):
        for value in ({}, {"rate_limits": None}, {"rate_limits": {}},
                      {"context_window": {"used_percentage": 20}}):
            with self.subTest(value=value):
                self.assertEqual(sources.parse_claude_limits(value), [])

    def test_invalid_numbers_and_windows_are_ignored(self):
        for value in (None, True, "25", float('nan'), float('inf'), [], {}):
            with self.subTest(value=value):
                self.assertEqual(sources.parse_claude_limits({"rate_limits": {
                    "five_hour": {"used_percentage": value}, "seven_day": "invalid"}}), [])

    def test_invalid_reset_values_do_not_break_rendering(self):
        for reset in (True, "tomorrow", 10**100):
            with self.subTest(reset=reset):
                result = sources.parse_claude_limits({"rate_limits": {
                    "five_hour": {"used_percentage": 0, "resets_at": reset}}})
                self.assertEqual(result[0].remaining_percent, 100)
                self.assertIsNone(result[0].resets_at)


class ClaudeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.state = Path(self.directory.name) / 'claude.json'
        self.path_patch = patch.object(sources, 'CLAUDE_STATE_FILE', self.state)
        self.path_patch.start()
        self.addCleanup(self.path_patch.stop)
        self.clock_patch = patch.object(sources.time, 'time', return_value=NOW)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def save(self, value):
        self.state.write_text(json.dumps(value))

    def test_missing_and_stale_snapshots_are_unavailable(self):
        self.assertEqual(sources.read_claude_limits(), [])
        for updated in (None, True, NOW - sources.CLAUDE_MAX_AGE - 1,
                        NOW + 61, float('nan'), 10**100):
            with self.subTest(updated=updated):
                self.save({**payload(), 'updated_at': updated})
                self.assertEqual(sources.read_claude_limits(), [])

    def test_expired_windows_are_removed_independently(self):
        value = payload()
        value['rate_limits']['five_hour']['resets_at'] = NOW
        self.save({**value, 'updated_at': NOW})
        self.assertEqual([item.window for item in sources.read_claude_limits()], ['7 dias'])


class ClaudeBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix='usage limit test ')
        self.addCleanup(self.directory.cleanup)
        self.state_root = Path(self.directory.name)
        self.state = self.state_root / 'usage-limit/claude.json'

    def bridge(self, value):
        return subprocess.run([sys.executable, str(ROOT / 'claude_usage_statusline.py')],
                              input=value if isinstance(value, str) else json.dumps(value),
                              text=True, capture_output=True, check=True,
                              env=dict(os.environ, XDG_STATE_HOME=str(self.state_root)))

    def test_real_command_persists_only_normalized_quota_data_privately(self):
        value = payload()
        value.update(session_id='private-synthetic-id', transcript_path='/private/synthetic.jsonl',
                     context_window={'used_percentage': 99})
        value['rate_limits']['five_hour']['unexpected'] = 'not-to-be-stored'
        result = self.bridge(value)
        saved = json.loads(self.state.read_text())
        self.assertEqual(set(saved), {'updated_at', 'rate_limits'})
        self.assertEqual(saved['rate_limits']['five_hour'],
                         {'used_percentage': 24, 'resets_at': NOW + 1800})
        self.assertNotIn('private', self.state.read_text())
        self.assertNotIn('not-to-be-stored', self.state.read_text())
        self.assertEqual(self.state.stat().st_mode & 0o777, 0o600)
        self.assertIn('5h 76% restante', result.stdout)
        self.assertEqual(result.stderr, '')
        self.assertEqual(list(self.state.parent.glob('.claude-*')), [])

    def test_early_session_unsupported_accounts_and_bad_json_do_not_create_state(self):
        for value in ({}, [], {'rate_limits': None}, 'not json', ''):
            with self.subTest(value=value):
                self.bridge(value)
                self.assertFalse(self.state.exists())

    def test_empty_rate_limits_replace_old_windows(self):
        self.bridge(payload())
        self.bridge({'rate_limits': {}})
        self.assertEqual(json.loads(self.state.read_text())['rate_limits'], {})

    def test_session_without_quota_cannot_reuse_a_previous_account_snapshot(self):
        self.bridge(payload())
        self.bridge({'context_window': {'used_percentage': 80}})
        self.assertFalse(self.state.exists())

    def test_unwritable_state_does_not_crash_the_status_line(self):
        (self.state_root / 'usage-limit').write_text('not a directory')
        result = self.bridge(payload())
        self.assertIn('indisponíveis', result.stdout)
        self.assertEqual(result.stderr, '')

    def test_bridge_reader_widget_and_panel_work_without_provider_accounts(self):
        import time
        value = payload()
        value['rate_limits']['five_hour']['resets_at'] = int(time.time()) + 1800
        value['rate_limits']['seven_day']['resets_at'] = int(time.time()) + 86400
        self.bridge(value)
        with patch.object(sources, 'CLAUDE_STATE_FILE', self.state):
            with patch.object(panel, 'read_codex_limits', side_effect=OSError), \
                 patch.object(panel, 'read_antigravity_limits', side_effect=ValueError), \
                 patch.object(panel, 'configured_profiles', return_value=[{'name': 'test', 'home': ''}]):
                limits, failed = panel.collect_limits()
            self.assertEqual(failed, {'Codex', 'Antigravity'})
            self.assertEqual(remaining_percent(group_limits(limits)['claude-code']), 59)
            window = SimpleNamespace(_collect_source=widget.UsageLimitWidget._collect_source,
                                     _finish_refresh=Mock())
            # Bind the source collector without creating a real GTK window.
            window._collect_source = lambda *args: widget.UsageLimitWidget._collect_source(window, *args)
            with patch.object(widget, 'read_codex_limits', side_effect=OSError), \
                 patch.object(widget, 'read_antigravity_limits', side_effect=ValueError), \
                 patch.object(widget.GLib, 'idle_add', side_effect=lambda callback, *args: callback(*args)):
                widget.UsageLimitWidget._load_limits(window, '', 1)
            args = window._finish_refresh.call_args.args
            self.assertEqual(args[0], 1)
            self.assertEqual([item.provider for item in args[1]], ['Claude Code', 'Claude Code'])
            self.assertFalse(args[2])


class ClaudePresentationTests(unittest.TestCase):
    def test_direct_and_antigravity_quotas_are_kept_separate(self):
        limits = sources.parse_claude_limits(payload())
        limits.append(sources.UsageLimit('Antigravity', 'Claude and GPT', 'weekly', 90))
        groups = group_limits(limits)
        self.assertEqual(remaining_percent(groups['claude-code']), 59)
        self.assertEqual(remaining_percent(groups['claude']), 10)

    def test_provider_cycle_includes_only_available_providers(self):
        for providers in ([], ['Claude Code'], ['Codex', 'Claude Code'], list(sources.SUPPORTED_PROVIDERS)):
            with self.subTest(providers=providers):
                limits = [sources.UsageLimit(name, name, '5h', 25) for name in providers]
                for current in [None, *providers]:
                    window = SimpleNamespace(_all_limits=limits, _active_provider=current)
                    result = widget.UsageLimitWidget._next_provider(window)
                    expected = None if not providers else providers[0] if current is None else providers[(providers.index(current) + 1) % len(providers)]
                    self.assertEqual(result, expected)

    def test_third_capsule_and_expanded_toggle_are_clickable(self):
        limits = [sources.UsageLimit(name, name, '5h', 25) for name in sources.SUPPORTED_PROVIDERS]
        self.assertEqual(dock.provider_at(40, dock.CAPSULE_TOPS[-1] + 30, limits), 'Claude Code')
        self.assertGreater(dock.COLLAPSED_HEIGHT, dock.CAPSULE_TOPS[-1] + dock.CAPSULE_HEIGHT)
        self.assertEqual(control_at(PROVIDER_TOGGLE[0] + 38, PROVIDER_TOGGLE[1]), 'provider')

    def test_claude_renders_in_both_themes(self):
        for dark in (False, True):
            with self.subTest(dark=dark):
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 240, 360)
                draw_widget(cairo.Context(surface), sources.parse_claude_limits(payload()), 0,
                            dark_mode=dark, active_provider='Claude Code',
                            available_providers={'Claude Code'})
                self.assertTrue(any(surface.get_data()))


if __name__ == '__main__':
    unittest.main()
