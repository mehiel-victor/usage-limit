# Usage Limit & Task Status

Lightweight GTK/Cairo floating widget showing usage limits and the status of
recent local Codex tasks. The floating `Limites | Tarefas` control switches
between provider usage and recent tasks; the circular attention button inside
the task view opens the active task queue. Codex limits are read
through its local `account/rateLimits/read`
app-server method. Antigravity is read through the documented structured
`agy -p /usage --output-format json` command; no credentials or provider
configuration files are accessed.

The widget refreshes every five minutes, supports manual refresh, click-to-cycle
windows, pinning, click-through, resize, theme detection, position persistence,
minimize/close, low-limit notifications, and a compact `C | A` toggle for
switching the displayed provider. Provider failures are tolerated
when another provider returns limits.
When click-through mode is enabled, the desktop receives clicks through the
donut; the floating controls remain interactive so the mode can be disabled.

The task view reads up to ten unarchived tasks every three seconds through one
persistent local app-server session. Unchanged rollout snapshots are cached and
the canvas repaints only when visible task status changes. Native active,
approval, user-input, and system-error states take precedence. Running and
completed states can also be derived from the rollout path and are identified
as inferred in segment tooltips. Click a segment, or select it with the arrow
keys and press Enter, to open the corresponding task in Codex Desktop. Click
the attention indicator, or press `A`, to open a rounded square queue with
running, queued, waiting, blocked, and failed tasks. Completed tasks stay out
of the queue. Each color-coded row opens its task directly in Codex Desktop.

The interface material adapts the optical language of
[Liquid Glass for GNOME Shell](https://github.com/ryohsuke1231/liquid-glass):
translucent volume, directional rim light, inner edge shading, and localized
specular highlights. The implementation is native Cairo/GTK and does not bundle or
require the GNOME Shell extension or its GLSL shaders.
Surfaces, text, rims, and shadows stay neutral; semantic color is reserved for
the donut meters, actionable controls, status indicators, badges, and legends.
No decorative gradient patterns are used; optical depth comes from uniform
transparency, edge highlights, and soft separation shadows.

## Requirements and launch

The launcher expects Python 3, GTK 3, PyGObject, and Cairo. Install and sign in
to at least one provider: Codex, or Antigravity CLI 1.1.8 or newer (the first
release with structured print output). Then run:

```bash
./launch-usage-limit
```

The guarded `install.sh` and `uninstall.sh` manage the
`io.github.mehiel.UsageLimit` desktop entry and `usage-limit` icon. The installer
migrates a previous managed Codex Token Widget entry only when its recorded
hashes still match; modified files are preserved.

## Multiple Codex accounts

Optional Codex profiles belong in
`${XDG_CONFIG_HOME:-~/.config}/usage-limit/config.json`:

```json
{
  "profiles": [
    {"name": "Trabalho", "home": "~/.codex-work"},
    {"name": "Pessoal", "home": "~/.codex-personal"}
  ]
}
```

The former `codex-token-window/config.json` remains a read-only fallback.
