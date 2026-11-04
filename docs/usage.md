# Usage & configuration

[Back to README](../README.md) · [Português (Brasil)](README.pt-BR.md)

## Providers

Install and authenticate at least one provider before launching. The widget refreshes usage every five minutes; right-click and choose `Atualizar agora` to refresh manually. Click the donut to cycle through a provider's available usage windows. The provider logo control cycles through available providers and is hidden when only one provider returns data.

### Codex

Usage comes from the local Codex app server's `account/rateLimits/read` method. The executable is discovered in the desktop installation, `~/.local/bin/codex`, or `PATH`. Codex task views use `thread/list` and local rollout metadata. Opening a task requires Codex Desktop and a registered `codex://` handler.

### Antigravity

The integration expects Antigravity CLI 1.1.8 or newer with structured usage output. It invokes `agy -p /usage --output-format json --print-timeout 30s`, with a 35-second process timeout. It looks for `~/.local/bin/agy`, then `PATH`. Sign in through the CLI; the widget does not read its credential or provider configuration files directly.

### Claude Code

Claude Code support uses its optional custom status-line command. Merge this into `~/.claude/settings.json`, replacing the example path with your checkout's absolute path:

```json
{
  "statusLine": {
    "type": "command",
    "command": "/absolute/path/to/usage-limit/claude_usage_statusline.py"
  }
}
```

This replaces an existing status-line command if you have one. The bridge receives Claude Code's status-line JSON and stores only `rate_limits` and an update timestamp at `${XDG_STATE_HOME:-~/.local/state}/usage-limit/claude.json`. It prints the 5-hour and 7-day usage summary for Claude Code's status line.

Claude remains unavailable until Claude Code sends a payload containing rate limits. The widget reads the latest saved snapshot; it does not query Claude directly or enforce a freshness threshold. If the values stop changing, check that the status-line command still runs and receives rate-limit fields.

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

Use `Alternar conta do Codex` in the context menu to cycle profiles. This selects the Codex home for usage and tasks; it does not change Antigravity or Claude accounts. Without configuration, the current Codex account is used. The former `codex-token-window/config.json` remains a read-only fallback.

## Desktop controls

The `Limites | Tarefas | Git` control selects the view. Right-click to refresh, switch provider/account, move to another monitor, collapse, minimize, or close. The small controls above it toggle click-through and pinning, resize by dragging, and collapse the widget.

| Action | Result |
| --- | --- |
| Drag the widget | Reposition it, including across monitors. |
| `Mover para outro monitor` | Cycle connected displays while preserving relative position. |
| Resize control | Resize within the current monitor's usable area, preserving the view's aspect ratio. |
| `Recolher na borda` | Show three provider capsules at the monitor's right edge. Unavailable providers show a dash. |
| Click a provider capsule | Expand into that provider's usage view. |
| Click-through | Send clicks through the donut while keeping floating controls interactive. |
| `Esc` | Close the widget. |

Expanded position and collapsed state are restored between launches. Theme colors follow the system's light/dark preference. The widget sends no desktop or lockscreen notifications.

## Codex tasks and Git worktrees

The task view polls up to ten unarchived Codex tasks every three seconds using one persistent local app-server process. Unchanged rollout snapshots are cached. Native active, approval, user-input, and system-error states take precedence; inferred running/completed states are identified in tooltips.

Click a task segment, or select it with arrow keys and press `Enter`, to open the task in Codex Desktop. Click the attention indicator or press `A` to open the active task queue. The queue includes running, queued, waiting, blocked, and failed tasks; completed tasks stay out.

The Git view discovers worktrees from directories referenced by monitored tasks. It runs read-only Git commands and compares branches with locally cached `origin/main`, falling back to `upstream/main` or local `main`. **Ahead-of-main counts do not prove commits are unpushed**: the reference may be stale, and a feature branch may already exist remotely. Tracked uncommitted changes are shown separately; untracked files are excluded. The widget does not fetch, merge, push, checkout, or modify worktrees.

## Data access and limitations

- The widget reads provider CLI output, Codex thread/rollout metadata, local Git state, and its own configuration/state. Task titles and working-directory paths can appear in the interface.
- It adds no telemetry or external collection endpoint. Provider processes handle their own authentication and may contact their services.
- Preferences and the Claude snapshot use the user's XDG directories. The installer stores its file manifest under `${XDG_DATA_HOME:-~/.local/share}/usage-limit/`.
- The launcher defaults to `GDK_BACKEND=x11`. Wayland sessions need XWayland; positioning, pinning, click-through, and multi-monitor behavior depend on the window manager. Native Wayland support is not provided.
- Provider output can change between CLI versions. A failed provider can remain unavailable while another returns data. Task status may be inferred rather than authoritative.

## Troubleshooting

If GTK imports fail, use your distribution's system Python with the packages listed in the [quick start](../README.md#quick-start). A virtual environment without system packages may not see PyGObject or Cairo. If provider usage is missing, confirm the CLI works in the same user's session and is discoverable at the paths above.

If the widget does not open on Wayland, check that XWayland is available. If task links do not open, check Codex Desktop's URL handler. For a broken application-menu shortcut after moving the checkout, run `./install.sh` again from its new location.

Optional diagnostics: run `USAGE_LIMIT_DEBUG=1 ./launch-usage-limit`. Debug messages are written to `/tmp/usage_limit_debug.log`. Inspect and redact logs, screenshots, task titles, paths, and provider output before sharing them. Report reproducible problems through [GitHub issues](https://github.com/mehiel-victor/usage-limit/issues); use the [security policy](../SECURITY.md) for sensitive reports.
