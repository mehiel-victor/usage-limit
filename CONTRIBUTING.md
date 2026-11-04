# Contributing to Usage Limit

Bug reports, documentation, Linux compatibility reports, tests, and focused
pull requests are welcome. English and Portuguese are both welcome.

## Find a place to start

- Browse [good first issues](https://github.com/mehiel-victor/usage-limit/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22).
- Report your desktop environment, display server, Python version, and provider
  version when sharing compatibility results.
- For a large feature or a new provider, open an issue first so we can agree on
  scope. Small fixes can go straight to a pull request.

## Run locally

Follow the [README](README.md#quick-start), fork the repository, then create a
branch for your change. Use the system Python with the distro's GTK bindings;
a plain virtual environment will not include them automatically.

There is no Python package install step. `./launch-usage-limit` runs the source.
Provider integrations need your own locally authenticated CLI. Never commit
credentials, account snapshots, task transcripts, or personal worktree paths.

## Code map

| Area | Files |
| --- | --- |
| Usage adapters and profiles | `usage_sources.py`, `claude_usage_statusline.py` |
| Task state and navigation | `task_sources.py`, `attention_queue_window.py` |
| GNOME panel and quota groups | `usage_limit_panel.py`, `panel_model.py`, `panel_icons.py` |
| Cairo views and branding | `usage_limit_view.py`, `task_status_view.py`, `collapsed_usage_view.py`, `model_branding.py` |
| Window behavior and notifications | `usage_limit_widget.py`, `collapsed_window_state.py`, `widget_support.py` |
| Desktop installation | `install.sh`, `install_panel.py`, `uninstall.sh`, `usage-limit.desktop.template` |

## Check your change

Run the same regression, syntax, and import checks used by CI. The panel check
also requires the optional Ayatana dependency documented in the README:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 -m compileall -q ./*.py
sh -n install.sh
sh -n uninstall.sh
sh -n launch-usage-limit-panel
bash -n launch-usage-limit
python3 -c 'import usage_limit_widget'
./launch-usage-limit-panel --check
git diff --check
```

CI checks quota grouping, panel icon rendering, installer preservation, widget
activation, the Claude Code status-line contract, Python/shell syntax, and imports
with GTK/Ayatana installed. Claude tests exercise the actual bridge command,
snapshot reader, widget collection, and panel collection using synthetic data.
Collapsed dock tests cover rendering, adaptive sizes, available-provider rows,
monitor edges, click regions, and expansion. Visibility tests keep real zero
quotas visible while hiding unavailable providers in the dock, selector, and panel.
It does not exercise provider accounts or a live GNOME desktop session.
Add tests alongside the existing `test_*.py` files without real credentials.

For behavior changes, add a regression test when practical and explain the
manual checks in your PR. Use synthetic provider responses instead of real
accounts in automated tests.

For visual changes, run the widget and check the affected view, light/dark
themes, resizing, and keyboard interaction. For window changes, also check
collapse/expand, click-through recovery, and monitor movement. Attach images
with fictitious or redacted data and identify their origin.

## Submit a pull request

Describe the problem, the resulting behavior, and what you checked. Keep the
change focused and follow the existing style. Documentation-only changes do
not need new tests. UI strings are currently in Portuguese; discuss localization
before introducing a second set of hardcoded labels.

Contributions are provided under the project's [MIT license](LICENSE).
Provider marks remain subject to their owners' rights; see [asset credits](assets/README.md).
Please follow the [code of conduct](CODE_OF_CONDUCT.md).
