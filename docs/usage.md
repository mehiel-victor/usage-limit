# Usage & configuration

[Back to README](../README.md) · [Português (Brasil)](README.pt-BR.md)

## Providers

Install and authenticate Codex, Antigravity, or both before launching. The widget refreshes usage every five minutes; right-click and choose `Atualizar agora` to refresh manually. Click the donut to cycle through usage windows. The `C | A` control and context menu switch between Codex and Antigravity.

### Codex

Usage comes from the local Codex app server's `account/rateLimits/read` method. The executable is discovered in the desktop installation, `~/.local/bin/codex`, or `PATH`. Task views use `thread/list` and local rollout metadata. Opening a task requires Codex Desktop and a registered `codex://` handler.

The quota belongs to the authenticated Codex account. It is not a measure of remaining ChatGPT conversation messages.

### Antigravity

The integration expects Antigravity CLI 1.1.8 or newer with structured usage output. It invokes `agy -p /usage --output-format json --print-timeout 30s`, with a 35-second process timeout. It looks for `~/.local/bin/agy`, then `PATH`. Sign in through the CLI; the widget does not read its credential or provider configuration files directly.

Gemini, Claude/GPT, and Argon quotas in the panel come from Antigravity's response. There is no direct Claude Code status-line bridge or separate Claude/GPT login in this version.

## GNOME/Ubuntu panel

The optional panel requires GTK 3, PyGObject, Ayatana AppIndicator, and active Ubuntu AppIndicators support in your desktop session. Install and launch from the repository root:

```bash
sudo apt install gir1.2-ayatanaappindicator3-0.1
./launch-usage-limit-panel --check
python3 install_panel.py
./launch-usage-limit-panel
```

`--check` validates imports; it does not test whether your desktop displays indicators. The installer creates a user application shortcut and an autostart entry for the next login. It preserves identical files and refuses to overwrite manual edits. Keep the checkout in place. Choose `Sair do indicador` before running `./uninstall.sh`; that removes managed widget and panel entries when their checksums still match.

| Group | Source |
| --- | --- |
| Codex | Codex quota windows across configured profiles. |
| Gemini | Antigravity groups whose model names contain Gemini, excluding Argon. |
| Claude/GPT | Antigravity groups whose model names contain Claude or GPT. |
| Argon | Antigravity groups whose model names contain Argon. |

Each indicator shows its logo and the **lowest remaining percentage** across its group's windows/accounts. Unknown quotas show `—`. Text is green at 60% or more, amber at 30–59%, and red below 30%. Color is accompanied by the percentage; the menu provides names, individual windows, reset times, and refresh/open-widget/quit actions. The panel refreshes every five minutes.

Logos and percentages are rendered together in 20-pixel-high images for Ubuntu AppIndicators. The launcher also searches `${XDG_DATA_HOME:-~/.local/share}/usage-limit/typelibs/` for typelibs when the native library is already installed. A typelib alone does not install that library.

## Multiple Codex accounts

Create `${XDG_CONFIG_HOME:-~/.config}/usage-limit/config.json` with profiles for Codex homes you already configured and authenticated:

```json
{
  "profiles": [
    {"name": "Work", "home": "~/.codex-work"},
    {"name": "Personal", "home": "~/.codex-personal"}
  ]
}
```

Use `Alternar conta do Codex` in the widget's context menu to cycle profiles. The panel aggregates configured Codex profiles. Neither changes your Antigravity account. Without configuration, the current Codex account is used. The former `codex-token-window/config.json` remains a read-only fallback.

## Desktop controls and tasks

The `Limites | Tarefas` control selects the view. Right-click to refresh, switch provider/account, move to another monitor, collapse, minimize, close, or enable lockscreen notices. Small controls above it toggle click-through and pinning, resize by dragging, and collapse the widget.

Drag across monitors or use `Mover para outro monitor` to cycle displays while preserving relative position. Resizing follows the current monitor's usable area and the view's aspect ratio. In click-through mode, the donut passes clicks to the desktop while the floating controls remain interactive.

`Recolher na borda` shows **two provider capsules** at the monitor's right edge. Each keeps its logo, remaining percentage, and usage bar. Click a capsule to expand into that provider. Position and collapsed state persist; explicitly opening the app expands/restores and presents the existing GTK instance. Theme colors follow the system light/dark preference. `Esc` closes the widget.

The task view polls up to ten unarchived Codex tasks every three seconds through one persistent local app server. Unchanged rollout snapshots are cached. Native active, approval, user-input, and system-error states take precedence; inferred running/completed states are identified in tooltips.

Click a task segment, or select with arrow keys and press `Enter`, to open it in Codex Desktop. The attention indicator or `A` opens the active task queue: running, queued, waiting, blocked, and failed tasks. Completed tasks stay out.

## Notifications

Desktop notifications require `notify-send` (`libnotify-bin` on Debian/Ubuntu) and a notification service.

- **Low limits:** a successful usage refresh sends a notification if any window has 20% or less remaining. Further refreshes can notify again while the limit stays low.
- **Approval:** a task entering a native Codex approval breakpoint sends one notification. Refreshes do not repeat it while the task remains there; leaving and re-entering can notify again.
- **Lockscreen, opt-in:** enable `Exibir no lockscreen` in the widget's context menu. After the initial task snapshot, new transitions into completed, waiting, blocked, or failed states publish a resident notification containing usage limits and affected task titles/activity. A periodic refresh alone does not republish it.

GNOME/KDE privacy settings may hide notification content while locked. Enable lockscreen content only if you want those task details visible there. The preference is saved in `${XDG_STATE_HOME:-~/.local/state}/usage-limit/lockscreen.json`.

## Data access and limitations

- The widget reads provider CLI output, Codex thread/rollout metadata, and its own configuration/state. Task titles and working-directory information can appear in the interface, diagnostics, or notifications.
- It adds no telemetry or external collection endpoint. Provider processes handle authentication and may contact their services.
- Widget preferences use XDG state directories. The panel caches rendered icons locally; installer manifests live under `${XDG_DATA_HOME:-~/.local/share}/usage-limit/`.
- The widget launcher defaults to `GDK_BACKEND=x11`. Wayland sessions need XWayland; positioning, pinning, click-through, and multiple monitors depend on the window manager. Native Wayland support is not provided.
- Provider output may change between CLI versions. A provider can fail while another returns data. Task status can be inferred rather than authoritative. The Git worktree view and direct Claude Code bridge from [v0.1.0](https://github.com/mehiel-victor/usage-limit/tree/v0.1.0) are not included in this version.

## Troubleshooting

For GTK/Cairo errors, install the [quick-start packages](../README.md#quick-start), including `python3-gi-cairo`, and use system Python. Plain virtual environments may not see distro bindings. The panel launcher uses `/usr/bin/python3`; its `--check` can identify missing Ayatana imports before installation.

For missing panel icons, check the desktop's AppIndicators extension/support after imports pass. For missing usage, confirm that the provider CLI works as the same user and is discoverable at the paths above. For broken task links, check Codex Desktop's URL handler. If you moved the checkout, rerun the relevant installer.

Optional diagnostics: `USAGE_LIMIT_DEBUG=1 ./launch-usage-limit` writes `/tmp/usage_limit_debug.log`. Review and redact provider output, task titles, paths, and screenshots before sharing. Use [GitHub issues](https://github.com/mehiel-victor/usage-limit/issues) for reproducible problems and the [security policy](../SECURITY.md) for sensitive reports.
