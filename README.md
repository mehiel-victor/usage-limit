# Usage Limit

**Keep AI usage limits and Codex tasks in view while you code.**

A floating Linux desktop widget for **Codex, Antigravity, and Claude Code**, with an optional **GNOME/Ubuntu top-bar indicator**. Built with Python, GTK 3, and Cairo.

[![Checks](https://github.com/mehiel-victor/usage-limit/actions/workflows/checks.yml/badge.svg)](https://github.com/mehiel-victor/usage-limit/actions/workflows/checks.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/mehiel-victor/usage-limit?style=social)](https://github.com/mehiel-victor/usage-limit/stargazers)

[Português (Brasil)](docs/README.pt-BR.md) · [Usage & configuration](docs/usage.md) · [Contribute](CONTRIBUTING.md) · [Releases](https://github.com/mehiel-victor/usage-limit/releases)

<picture>
  <source media="(prefers-color-scheme: light)" srcset="assets/preview-light.png">
  <img alt="Usage Limit showing provider usage, Codex task status, the compact dock, and GNOME panel badges" src="assets/preview.png">
</picture>

*Preview rendered by the app's Cairo drawing code with sample data. The current interface is in Portuguese.*

## What you get

- **Usage at a glance:** remaining percentages and reset times from supported providers; cycle through available windows and providers.
- **Codex task status:** recent tasks, an active task queue, and direct links back to Codex Desktop.
- **GNOME top-bar quotas:** separate groups for Codex, Gemini, Antigravity Claude/GPT, Gemini 4 Argon, and direct Claude Code, shown only when quota data is available.
- **A compact left-edge dock:** smaller black capsules sized for your monitor, with one row per available provider; click to expand.
- **Desktop controls and alerts:** pinning, click-through, resize, monitor switching, saved position, approval/low-limit notifications, and opt-in lockscreen task notices.

The widget adds no telemetry. It reads provider CLI output and local task data; provider CLIs may contact their own services. Claude/GPT and Argon quotas come from Antigravity, without separate logins. Codex quotas do not represent ChatGPT conversation limits. See [data access and limitations](docs/usage.md#data-access-and-limitations).

## Quick start

Requires **Linux, Python 3.10+, GTK 3, PyGObject, and Cairo**, plus at least one configured provider. The launcher defaults to **X11**; Wayland sessions need **XWayland**. Native Wayland, macOS, and Windows support are not provided.

On Debian/Ubuntu, install the system dependencies:

```bash
sudo apt update
sudo apt install git python3 python3-gi python3-gi-cairo python3-cairo gir1.2-gtk-3.0 librsvg2-common libnotify-bin
```

Then clone and launch:

```bash
git clone https://github.com/mehiel-victor/usage-limit.git
cd usage-limit
./launch-usage-limit
```

| Provider | Setup |
| --- | --- |
| Codex | Install Codex and sign in. The widget reads usage through its local app server. |
| Antigravity | Install and sign in to the Antigravity CLI with structured `/usage` output. |
| Claude Code | Configure the optional [local status-line bridge](docs/usage.md#claude-code) for an eligible account. |

Another working provider can still supply usage data when one fails. Codex task links require Codex Desktop and its `codex://` URL handler. Reopening the widget restores and presents its existing instance.

Claude Code support is tested with synthetic payloads; an authenticated Claude Code session has not been validated. Providers without valid quota data are hidden, including missing, stale, or reset Claude windows. A real 0% remaining quota stays visible.

## Optional GNOME/Ubuntu panel

Enable Ubuntu AppIndicators support in your desktop session, then run from the checkout:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
./launch-usage-limit-panel --check
python3 install_panel.py
./launch-usage-limit-panel
```

The panel installer adds an application shortcut and **starts the indicator at login**. Keep this checkout in place. [Panel details and notifications](docs/usage.md#gnomeubuntu-panel) explain grouping, status colors, and lockscreen behavior.

## Add it to your app launcher

```bash
./install.sh
```

This registers the floating widget's desktop entry and icon for the current user. It points to this checkout, so keep the folder in place. It does not install dependencies or enable widget autostart.

Update with `git pull --ff-only`, then restart the widget. Remove the managed launcher and icon with:

```bash
./uninstall.sh
```

Quit the panel through `Sair do indicador` before uninstalling. The uninstaller removes both installers' managed entries, preserving modified files. It does not delete your checkout, provider configuration, or widget preferences.

Upgrading from [v0.1.0](https://github.com/mehiel-victor/usage-limit/tree/v0.1.0)? The Git view is no longer included. The Claude Code bridge now normalizes quota fields and expires stale snapshots; direct Claude Code usage is separate from Antigravity's Claude/GPT group.

## Make your first contribution

Bug reports, installation feedback, documentation, translations, and code are welcome. Start with the [contribution guide](CONTRIBUTING.md) and [good first issues](https://github.com/mehiel-victor/usage-limit/issues?q=is%3Aissue%20is%3Aopen%20label%3A%22good%20first%20issue%22).

Useful areas include distro setup guides, parser tests using sanitized fixtures, and broader desktop compatibility. Please describe your Linux distribution and desktop session when reporting a problem.

To run tests and basic syntax checks:

```bash
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 -m compileall -q ./*.py
sh -n install.sh
sh -n uninstall.sh
bash -n launch-usage-limit
sh -n launch-usage-limit-panel
```

The suite covers panel grouping/icons, widget activation, and the Claude bridge through the widget/panel using synthetic payloads. It does not replace desktop or authenticated provider tests. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full validation workflow.

If Usage Limit is useful to you, a star helps others discover it. Sharing your setup and contributing a fix helps the project grow.

## License & credits

Code is available under the [MIT License](LICENSE). Provider marks remain the property of their respective owners; see [asset credits](assets/README.md). This is an independent community project, not an official product of OpenAI, Google, or Anthropic.

The visual treatment draws inspiration from [Liquid Glass for GNOME Shell](https://github.com/ryohsuke1231/liquid-glass); no extension or shaders are required. Read the [Code of Conduct](CODE_OF_CONDUCT.md) and [security policy](SECURITY.md) before participating.
