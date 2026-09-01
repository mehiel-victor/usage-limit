#!/usr/bin/env python3
"""Always-on-top display of provider usage limits."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Optional

from attention_queue_window import AttentionQueueWindow
from collapsed_usage_view import (
    COLLAPSED_HEIGHT,
    COLLAPSED_WIDTH,
    draw_collapsed_widget,
    provider_at,
    provider_remaining,
    right_edge_position,
)
from collapsed_window_state import CollapsedWindowState
from usage_sources import UsageLimit, configured_profiles, notify, read_antigravity_limits, read_codex_limits
from task_sources import CodexTaskSource, MonitoredTask, open_codex_task
from task_status_view import (
    ATTENTION_BUTTON_CENTER,
    attention_button_at,
    draw_mode_toggle,
    draw_task_status,
    mode_at,
    segment_at,
    task_tooltip,
    visible_tasks,
)
from usage_limit_view import (
    COLLAPSE_CONTROL,
    MIN_WIDGET_SIZE,
    PASSTHROUGH_CONTROL,
    PIN_CONTROL,
    PROVIDER_TOGGLE,
    RESIZE_CONTROL,
    WIDGET_HEIGHT,
    WIDGET_SIZE,
    draw_widget,
    _draw_utility_controls,
    clamp_widget_size,
    clamp_window_position,
    control_at,
    control_region,
    next_monitor_position,
    outward_resize_delta,
    system_prefers_dark,
    theme_colors,
    widget_height,
)
from widget_support import (
    approval_task_transitions, format_lockscreen_status, log_debug,
    notify_lockscreen, publish_approval_notifications, task_visual_signature,
    unread_task_transitions,
)

PROVIDER_ERRORS = (OSError, ValueError, TimeoutError, json.JSONDecodeError, RuntimeError, subprocess.SubprocessError)

try:
    import cairo
except ImportError:
    cairo = None  # type: ignore[assignment]

try:
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gdk, Gio, GLib, Gtk
except (ImportError, ValueError):
    Gdk = Gio = GLib = Gtk = None  # type: ignore[assignment]

POSITION_FILE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "usage-limit" / "position.json"
LOCKSCREEN_FILE = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "usage-limit" / "lockscreen.json"
LEGACY_POSITION_FILE = Path.home() / ".codex" / "token_widget_position.json"
RUNTIME_ROOT = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
LOCK_FILE = Path(RUNTIME_ROOT) / "usage-limit" / "widget.lock"
REFRESH_MS = 5 * 60_000
TASK_REFRESH_MS = 3_000


class UsageLimitWidget(CollapsedWindowState, Gtk.Window if Gtk is not None else object):
    def __init__(self, application: Any = None):
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        if application is not None:
            self.set_application(application)
        self._position_file = POSITION_FILE
        self._all_limits: list[UsageLimit] = []
        self._limits: list[UsageLimit] = []
        self._active_provider: Optional[str] = None
        self._selected_limit = 0
        self._error = False
        self._critical_phase = False
        self._refreshing = False
        self._refresh_generation = 0
        self._press_origin: Optional[tuple[float, float]] = None
        self._press_target: Optional[str] = None
        self._resize_start_size = WIDGET_SIZE
        self._did_drag = False
        self._hovered_control: Optional[str] = None
        self._pinned = True
        self._click_through = False
        self._dark_mode = True
        self._interface_settings: Optional[Any] = None
        self._gtk_settings: Optional[Any] = None
        self._visibility_check_pending = False
        self._widget_size = WIDGET_SIZE
        self._minimized = False
        self._collapsed = False
        self._expanded_position: Optional[tuple[int, int]] = None
        self._profiles = configured_profiles()
        self._profile_index = 0
        self._task_source = CodexTaskSource(self._profiles[0]["home"])
        self._view_mode = "usage"
        self._tasks: list[MonitoredTask] = []
        self._task_error = False
        self._task_refreshing = False
        self._selected_task = 0
        self._attention_window: Optional[Any] = None
        self._lockscreen_enabled = self._load_lockscreen_preference()
        self._known_task_statuses: dict[str, str] = {}
        self._known_approval_task_ids: set[str] = set()
        self._task_statuses_initialized = False
        self._lockscreen_notification_id = 0

        self.set_title("Usage Limit")
        self.set_icon_name("usage-limit")
        self.set_default_size(WIDGET_SIZE, WIDGET_HEIGHT)
        self.set_size_request(MIN_WIDGET_SIZE, widget_height(MIN_WIDGET_SIZE))
        self.set_resizable(True)
        self.set_decorated(False)
        self.set_keep_above(self._pinned)
        self.set_skip_taskbar_hint(False)
        self.set_skip_pager_hint(True)
        self.set_type_hint(Gdk.WindowTypeHint.NORMAL)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self._configure_system_theme()

        self.area = Gtk.DrawingArea()
        self.area.set_size_request(MIN_WIDGET_SIZE, widget_height(MIN_WIDGET_SIZE))
        self.area.set_has_tooltip(True)
        self.area.set_can_focus(True)
        self.area.get_accessible().set_name("Limites de uso e status de tarefas")
        self.area.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK
            | Gdk.EventMask.BUTTON_RELEASE_MASK
            | Gdk.EventMask.POINTER_MOTION_MASK
            | Gdk.EventMask.LEAVE_NOTIFY_MASK
        )
        self.area.connect("draw", self._on_draw)
        self.area.connect("button-press-event", self._on_press)
        self.area.connect("motion-notify-event", self._on_motion)
        self.area.connect("button-release-event", self._on_release)
        self.area.connect("leave-notify-event", self._on_leave)
        self.area.connect("query-tooltip", self._on_tooltip)
        self.add(self.area)
        self._context_menu = self._build_context_menu()
        self.connect("key-press-event", self._on_key)
        self.connect("map-event", self._on_map)
        self.connect("configure-event", self._on_configure)
        self.connect("size-allocate", self._on_size_allocate)
        self.connect("window-state-event", self._on_window_state)
        self._restore_position()
        self.refresh()
        self.refresh_tasks()
        GLib.timeout_add_seconds(REFRESH_MS // 1000, self._scheduled_refresh)
        GLib.timeout_add(TASK_REFRESH_MS, self._scheduled_task_refresh)
        GLib.timeout_add(450, self._critical_blink)

    def _render_limits(self, limits: list[UsageLimit]) -> None:
        self._all_limits = limits
        providers = {limit.provider for limit in limits}
        if self._active_provider not in providers:
            self._active_provider = next((provider for provider in ("Codex", "Antigravity") if provider in providers), None)
        self._limits = [limit for limit in limits if limit.provider == self._active_provider]
        self._selected_limit = max(0, min(self._selected_limit, len(self._limits) - 1))
        self._error = False
        self._critical_phase = False
        self.area.queue_draw()

    def _on_draw(self, _area: Any, context: Any) -> bool:
        allocation = self.area.get_allocation()
        if self._collapsed:
            scale = min(allocation.width / COLLAPSED_WIDTH, allocation.height / COLLAPSED_HEIGHT)
            context.save()
            context.scale(scale, scale)
            hovered_provider = None
            if self._hovered_control and self._hovered_control.startswith("collapsed:"):
                hovered_provider = self._hovered_control.split(":", 1)[1]
            draw_collapsed_widget(context, self._all_limits, hovered_provider, self._dark_mode)
            context.restore()
            return False
        scale = min(allocation.width / WIDGET_SIZE, allocation.height / WIDGET_HEIGHT)
        context.save()
        context.scale(scale, scale)
        if self._view_mode == "usage":
            draw_widget(
                context,
                self._limits,
                self._selected_limit,
                self._error,
                self._pinned,
                self._hovered_control,
                self._click_through,
                self._dark_mode,
                self._active_provider,
                {limit.provider for limit in self._all_limits},
                self._critical_phase and self._has_critical_limit(),
            )
            draw_mode_toggle(context, self._view_mode, self._hovered_control, self._dark_mode)
        else:
            draw_task_status(
                context,
                self._tasks,
                self._view_mode,
                self._selected_task,
                self._hovered_control,
                self._task_error,
                self._dark_mode,
            )
            _draw_utility_controls(
                context,
                self._pinned,
                self._click_through,
                self._hovered_control,
                theme_colors(self._dark_mode),
            )
        context.restore()
        return False

    def _has_critical_limit(self) -> bool:
        return any(limit.remaining_percent <= 20 for limit in self._all_limits)

    def _critical_blink(self) -> bool:
        if self._collapsed or self._view_mode != "usage":
            self._critical_phase = False
            return True
        if self._error or not self._has_critical_limit():
            if self._critical_phase:
                self._critical_phase = False
                self.area.queue_draw()
            return True
        self._critical_phase = not self._critical_phase
        self.area.queue_draw()
        return True

    def _base_point(self, x: float, y: float) -> tuple[float, float]:
        allocation = self.area.get_allocation()
        base_width = COLLAPSED_WIDTH if self._collapsed else WIDGET_SIZE
        base_height = COLLAPSED_HEIGHT if self._collapsed else WIDGET_HEIGHT
        scale = min(allocation.width / base_width, allocation.height / base_height)
        return x / scale, y / scale

    def _configure_system_theme(self) -> None:
        """Follow the system GTK appearance and repaint when it changes."""
        self._gtk_settings = Gtk.Settings.get_default()
        if self._gtk_settings is not None:
            self._gtk_settings.set_property("gtk-enable-animations", False)
            self._gtk_settings.connect("notify::gtk-theme-name", self._on_system_theme_changed)
            self._gtk_settings.connect(
                "notify::gtk-application-prefer-dark-theme",
                self._on_system_theme_changed,
            )
        try:
            schema_source = Gio.SettingsSchemaSource.get_default()
            schema = schema_source.lookup("org.gnome.desktop.interface", True) if schema_source else None
            if schema is not None:
                self._interface_settings = Gio.Settings.new("org.gnome.desktop.interface")
                self._interface_settings.connect("changed::color-scheme", self._on_system_theme_changed)
                self._interface_settings.connect("changed::gtk-theme", self._on_system_theme_changed)
        except GLib.Error:
            self._interface_settings = None
        self._sync_system_theme()
        self._apply_native_theme_preference()

    def _sync_system_theme(self) -> None:
        color_scheme = "default"
        gtk_theme = ""
        if self._interface_settings is not None:
            color_scheme = self._interface_settings.get_string("color-scheme")
            gtk_theme = self._interface_settings.get_string("gtk-theme")
        gtk_settings = self._gtk_settings
        if gtk_settings is not None:
            gtk_theme = gtk_settings.get_property("gtk-theme-name") or gtk_theme
        gtk_prefers_dark = bool(gtk_settings.get_property("gtk-application-prefer-dark-theme")) if gtk_settings else False
        self._dark_mode = system_prefers_dark(color_scheme, gtk_theme, gtk_prefers_dark)

    def _apply_native_theme_preference(self) -> None:
        """Let GTK render native menus using the same system appearance."""
        if self._gtk_settings is None:
            return
        preferred = bool(self._gtk_settings.get_property("gtk-application-prefer-dark-theme"))
        if preferred != self._dark_mode:
            self._gtk_settings.set_property("gtk-application-prefer-dark-theme", self._dark_mode)

    def _on_system_theme_changed(self, _settings: Any, _key: str) -> None:
        previous = self._dark_mode
        self._sync_system_theme()
        self._apply_native_theme_preference()
        if self._dark_mode != previous:
            self.area.queue_draw()
            if self._attention_window is not None:
                self._attention_window.update_tasks(self._tasks, self._dark_mode)

    def _on_press(self, _area: Any, event: Any) -> bool:
        if event.button == 3:
            self._context_menu.popup_at_pointer(event)
            return True
        if event.button != 1:
            return False
        self._press_origin = (event.x_root, event.y_root)
        base_x, base_y = self._base_point(event.x, event.y)
        if self._collapsed:
            provider = provider_at(base_x, base_y)
            self._press_target = f"collapsed:{provider}" if provider else None
            self._did_drag = False
            return True
        selected_mode = mode_at(base_x, base_y)
        self._press_target = f"mode:{selected_mode}" if selected_mode else control_at(base_x, base_y)
        if self._view_mode != "usage" and self._press_target == "provider":
            self._press_target = None
        shown_tasks = visible_tasks(self._tasks, self._view_mode)
        if self._view_mode != "usage" and self._press_target is None:
            task_index = segment_at(base_x, base_y, len(shown_tasks))
            if task_index is not None:
                self._press_target = f"task:{task_index}"
            elif attention_button_at(base_x, base_y):
                self._press_target = "attention-button"
        log_debug(f"Press at raw=({event.x}, {event.y}) base=({base_x}, {base_y}) target={self._press_target}")
        self._resize_start_size = self._widget_size
        self._did_drag = False
        return True

    def _build_context_menu(self) -> Any:
        menu = Gtk.Menu()
        refresh = Gtk.MenuItem.new_with_label("Atualizar agora")
        refresh.connect("activate", lambda _item: self.refresh())
        menu.append(refresh)
        toggle_prov = Gtk.MenuItem.new_with_label("Alternar provedor (Codex / Antigravity)")
        toggle_prov.connect("activate", lambda _item: self._toggle_provider())
        menu.append(toggle_prov)
        if len(self._profiles) > 1:
            account = Gtk.MenuItem.new_with_label("Alternar conta do Codex")
            account.connect("activate", lambda _item: self._next_account())
            menu.append(account)
        lockscreen = Gtk.CheckMenuItem.new_with_label("Exibir no lockscreen")
        lockscreen.set_active(self._lockscreen_enabled)
        lockscreen.connect("toggled", self._toggle_lockscreen)
        menu.append(lockscreen)
        move_monitor = Gtk.MenuItem.new_with_label("Mover para outro monitor")
        move_monitor.set_sensitive(len(self._monitor_workareas()) > 1)
        move_monitor.connect("activate", lambda _item: self._move_to_next_monitor())
        menu.append(move_monitor)
        self._collapse_menu_item = Gtk.MenuItem.new_with_label("Recolher na borda")
        self._collapse_menu_item.connect("activate", lambda _item: self._toggle_collapsed())
        menu.append(self._collapse_menu_item)
        menu.append(Gtk.SeparatorMenuItem())
        minimize = Gtk.MenuItem.new_with_label("Minimizar")
        minimize.connect("activate", lambda _item: self._minimize())
        close = Gtk.MenuItem.new_with_label("Fechar")
        close.connect("activate", lambda _item: self.close())
        menu.append(minimize)
        menu.append(Gtk.SeparatorMenuItem())
        menu.append(close)
        menu.show_all()
        return menu

    def _load_lockscreen_preference(self) -> bool:
        try:
            value = json.loads(LOCKSCREEN_FILE.read_text(encoding="utf-8"))
            return bool(value.get("enabled")) if isinstance(value, dict) else False
        except (OSError, ValueError):
            return False

    def _toggle_lockscreen(self, item: Any) -> None:
        self._lockscreen_enabled = bool(item.get_active())
        try:
            LOCKSCREEN_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOCKSCREEN_FILE.write_text(
                json.dumps({"enabled": self._lockscreen_enabled}) + "\n",
                encoding="utf-8",
            )
        except OSError:
            return

    def _publish_lockscreen(self, unread_tasks: list[MonitoredTask]) -> None:
        if not self._lockscreen_enabled or not unread_tasks:
            return
        self._lockscreen_notification_id = notify_lockscreen(
            format_lockscreen_status(self._all_limits, unread_tasks),
            self._lockscreen_notification_id,
        )

    def _next_account(self) -> None:
        self._profile_index = (self._profile_index + 1) % len(self._profiles)
        self._task_source.close()
        self._task_source = CodexTaskSource(self._profiles[self._profile_index]["home"])
        self._task_refreshing = False
        self._known_task_statuses = {}
        self._known_approval_task_ids = set()
        self._task_statuses_initialized = False
        self._all_limits = []
        self._limits = []
        self._error = False
        self.refresh(force=True)
        self.refresh_tasks()

    def _on_motion(self, _area: Any, event: Any) -> bool:
        if self._collapsed:
            if self._press_origin is None:
                base_x, base_y = self._base_point(event.x, event.y)
                provider = provider_at(base_x, base_y)
                hovered = f"collapsed:{provider}" if provider else None
                if hovered != self._hovered_control:
                    self._hovered_control = hovered
                    self._update_cursor()
                    self.area.queue_draw()
            return True
        if self._press_origin and self._press_target == "resize":
            delta_x = event.x_root - self._press_origin[0]
            delta_y = event.y_root - self._press_origin[1]
            delta = outward_resize_delta(delta_x, delta_y)
            new_size = clamp_widget_size(self._resize_start_size + delta)
            self._did_drag = self._did_drag or new_size != self._resize_start_size
            if new_size != self._widget_size:
                self._widget_size = new_size
                self.resize(new_size, widget_height(new_size))
            return True
        if self._press_origin and self._press_target is None and not self._did_drag:
            moved = abs(event.x_root - self._press_origin[0]) > 5 or abs(event.y_root - self._press_origin[1]) > 5
            if moved:
                self._did_drag = True
                self.begin_move_drag(1, round(event.x_root), round(event.y_root), event.time)
            return True
        if self._press_origin is None:
            base_x, base_y = self._base_point(event.x, event.y)
            selected_mode = mode_at(base_x, base_y)
            hovered = f"mode:{selected_mode}" if selected_mode else control_at(base_x, base_y)
            if self._view_mode != "usage" and hovered == "provider":
                hovered = None
            if self._view_mode != "usage" and hovered is None:
                task_index = segment_at(base_x, base_y, len(visible_tasks(self._tasks, self._view_mode)))
                hovered = f"task:{task_index}" if task_index is not None else None
                if hovered is None and attention_button_at(base_x, base_y):
                    hovered = "attention-button"
            if hovered != self._hovered_control:
                self._hovered_control = hovered
                self._update_cursor()
                self.area.queue_draw()
        return True

    def _on_release(self, _area: Any, event: Any) -> bool:
        if event.button != 1:
            return False
        target = self._press_target
        log_debug(f"Release target={target} did_drag={self._did_drag}")
        self._press_origin = None
        self._press_target = None
        if not self._did_drag:
            if target and target.startswith("collapsed:"):
                self._expand_from_provider(target.split(":", 1)[1])
            elif target and target.startswith("mode:"):
                self._set_view_mode(target.split(":", 1)[1])
            elif target and target.startswith("task:"):
                task_index = int(target.split(":", 1)[1])
                shown_tasks = visible_tasks(self._tasks, self._view_mode)
                if task_index < len(shown_tasks):
                    self._selected_task = task_index
                    open_codex_task(shown_tasks[task_index].id)
            elif target == "attention-button":
                self._open_attention_queue()
            elif self._view_mode != "usage" and self._task_error:
                self.refresh_tasks()
            elif target == "provider":
                self._toggle_provider()
            elif target == "pin":
                self._pinned = not self._pinned
                self._apply_window_layer()
                self.area.queue_draw()
            elif target == "passthrough":
                self._click_through = not self._click_through
                self._apply_input_region()
                self.area.queue_draw()
            elif target == "resize":
                return True
            elif target == "collapse":
                self._toggle_collapsed()
            elif len(self._limits) > 1:
                self._selected_limit = (self._selected_limit + 1) % len(self._limits)
                self.area.queue_draw()
            elif not self._limits or self._error:
                self.refresh()
        return True

    def _on_leave(self, _area: Any, _event: Any) -> bool:
        if self._press_origin is None and self._hovered_control is not None:
            self._hovered_control = None
            self._update_cursor()
            self.area.queue_draw()
        return False

    def _on_tooltip(self, _area: Any, x: int, y: int, _keyboard_mode: bool, tooltip: Any) -> bool:
        base_x, base_y = self._base_point(x, y)
        if self._collapsed:
            provider = provider_at(base_x, base_y)
            if provider is None:
                return False
            remaining = provider_remaining(self._all_limits, provider)
            status = "indisponível" if remaining is None else f"{remaining}% restante"
            tooltip.set_text(f"{provider}: {status}. Clique para expandir.")
            return True
        selected_mode = mode_at(base_x, base_y)
        target = f"mode:{selected_mode}" if selected_mode else control_at(base_x, base_y)
        if self._view_mode != "usage" and target == "provider":
            target = None
        over_attention = self._view_mode != "usage" and attention_button_at(base_x, base_y)
        task_index = None
        shown_tasks = visible_tasks(self._tasks, self._view_mode)
        if self._view_mode != "usage" and target is None and not over_attention:
            task_index = segment_at(base_x, base_y, len(shown_tasks))
        if over_attention:
            tooltip.set_text("Abrir fila de tarefas ativas")
        elif task_index is not None:
            tooltip.set_text(task_tooltip(shown_tasks[task_index]))
        elif target and target.startswith("mode:"):
            labels = {
                "usage": "Mostrar limites de uso",
                "overview": "Mostrar tarefas",
            }
            tooltip.set_text(labels[target.split(":", 1)[1]])
        elif target == "provider":
            providers = {limit.provider for limit in self._all_limits}
            if len(providers) < 2:
                if len(providers) == 1:
                    tooltip.set_text(f"Apenas {next(iter(providers))} está disponível")
                else:
                    tooltip.set_text(
                        "Provedores indisponíveis" if self._error else "Carregando provedores"
                    )
            else:
                next_provider = "Antigravity" if self._active_provider == "Codex" else "Codex"
                tooltip.set_text(f"Mostrar limites do {next_provider}")
        elif target == "pin":
            tooltip.set_text("Desfixar da tela" if self._pinned else "Fixar na tela")
        elif target == "passthrough":
            tooltip.set_text("Desativar modo intangível" if self._click_through else "Ativar modo intangível")
        elif target == "resize":
            tooltip.set_text("Arraste para redimensionar")
        elif target == "collapse":
            tooltip.set_text("Recolher na borda direita")
        else:
            return False
        return True

    def _set_view_mode(self, mode: str) -> None:
        if mode not in {"usage", "overview", "attention"} or mode == self._view_mode:
            return
        self._view_mode = mode
        self._selected_task = 0
        if mode != "usage":
            self.refresh_tasks()
        if self._click_through:
            GLib.idle_add(self._apply_input_region)
        self._save_position()
        self.area.queue_draw()

    def _open_attention_queue(self) -> None:
        if self._attention_window is not None:
            self._attention_window.present()
            return
        window = AttentionQueueWindow(
            self,
            self._tasks,
            self._dark_mode,
            open_codex_task,
        )
        self._attention_window = window
        window.connect("destroy", self._on_attention_window_destroyed)
        window.show_all()
        window.present()

    def _on_attention_window_destroyed(self, _window: Any) -> None:
        self._attention_window = None

    def _toggle_provider(self) -> None:
        providers = {limit.provider for limit in self._all_limits}
        log_debug(f"Toggle provider: all_limits={[(l.provider, l.name) for l in self._all_limits]}, providers={providers}")
        if len(providers) < 2:
            return
        self._active_provider = "Antigravity" if self._active_provider == "Codex" else "Codex"
        self._limits = [limit for limit in self._all_limits if limit.provider == self._active_provider]
        self._selected_limit = min(self._selected_limit, max(0, len(self._limits) - 1))
        log_debug(f"Switched provider to: {self._active_provider}, new limits length: {len(self._limits)}")
        self.area.queue_draw()

    def _update_cursor(self) -> None:
        window = self.area.get_window()
        if window is None:
            return
        provider_disabled = self._hovered_control == "provider" and len(
            {limit.provider for limit in self._all_limits}
        ) < 2
        cursor_name = "default"
        if self._hovered_control == "resize":
            cursor_name = "ne-resize"
        elif self._hovered_control and not provider_disabled:
            cursor_name = "pointer"
        window.set_cursor(Gdk.Cursor.new_from_name(self.get_display(), cursor_name))

    def _on_key(self, _widget: Any, event: Any) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.close()
            return True
        if self._collapsed and event.keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space}:
            self._expand_from_provider(self._active_provider or "Codex")
            return True
        if self._view_mode != "usage" and event.keyval in {Gdk.KEY_Left, Gdk.KEY_Right}:
            tasks = visible_tasks(self._tasks, self._view_mode)
            if tasks:
                direction = -1 if event.keyval == Gdk.KEY_Left else 1
                self._selected_task = (self._selected_task + direction) % len(tasks)
                self.area.queue_draw()
            return True
        if self._view_mode != "usage" and event.keyval in {Gdk.KEY_a, Gdk.KEY_A}:
            self._open_attention_queue()
            return True
        if self._view_mode != "usage" and event.keyval in {Gdk.KEY_Return, Gdk.KEY_KP_Enter}:
            tasks = visible_tasks(self._tasks, self._view_mode)
            if tasks:
                open_codex_task(tasks[min(self._selected_task, len(tasks) - 1)].id)
            return True
        return False

    def _on_map(self, _widget: Any, _event: Any) -> bool:
        GLib.idle_add(self._apply_window_layer)
        GLib.idle_add(self._apply_input_region)
        self._queue_visibility_check()
        return False

    def _on_configure(self, _widget: Any, _event: Any) -> bool:
        self._queue_visibility_check()
        return False

    def _queue_visibility_check(self) -> None:
        if not self._visibility_check_pending:
            self._visibility_check_pending = True
            GLib.idle_add(self._ensure_visible)

    def _monitor_workareas(self) -> list[tuple[int, int, int, int]]:
        display = self.get_display()
        workareas = []
        for index in range(display.get_n_monitors()):
            rectangle = display.get_monitor(index).get_workarea()
            workareas.append((rectangle.x, rectangle.y, rectangle.width, rectangle.height))
        return workareas

    def _pointer_position(self) -> Optional[tuple[int, int]]:
        if self._press_origin is None:
            return None
        pointer = self.get_display().get_default_seat().get_pointer()
        if pointer is None:
            return None
        _screen, pointer_x, pointer_y = pointer.get_position()
        return pointer_x, pointer_y

    def _move_to_next_monitor(self) -> None:
        x, y = self.get_position()
        width, height = self.get_size()
        target_x, target_y = next_monitor_position(
            x,
            y,
            width,
            height,
            self._monitor_workareas(),
        )
        self._remember_expanded_position_on_monitor(target_x, target_y)
        self.move(target_x, target_y)
        self._save_position((target_x, target_y))

    def _ensure_visible(self) -> bool:
        self._visibility_check_pending = False
        if not self.get_realized():
            return False
        x, y = self.get_position()
        width, height = self.get_size()
        if self._collapsed:
            safe_x, safe_y = right_edge_position(
                x,
                y,
                width,
                height,
                self._monitor_workareas(),
            )
            if (safe_x, safe_y) != (x, y):
                self.move(safe_x, safe_y)
            return False
        safe_x, safe_y = clamp_window_position(
            x,
            y,
            width,
            height,
            self._monitor_workareas(),
            self._pointer_position(),
        )
        if (safe_x, safe_y) != (x, y):
            self.move(safe_x, safe_y)
        return False

    def _on_size_allocate(self, _widget: Any, _allocation: Any) -> None:
        GLib.idle_add(self._apply_input_region)

    def _on_window_state(self, _widget: Any, event: Any) -> bool:
        self._minimized = bool(event.new_window_state & Gdk.WindowState.ICONIFIED)
        if not self._minimized:
            self.set_skip_taskbar_hint(self._collapsed)
            GLib.idle_add(self._apply_window_layer)
        return False

    def _minimize(self) -> None:
        self.set_skip_taskbar_hint(False)
        self.iconify()

    def _apply_window_layer(self) -> bool:
        keep_above = self._pinned or self._collapsed
        self.set_keep_above(keep_above)
        if keep_above:
            self.stick()
        else:
            self.unstick()
        window = self.get_window()
        if window is not None:
            window.set_keep_above(keep_above)
        return False

    def _apply_input_region(self) -> bool:
        """Keep the controls clickable while optionally passing circle clicks through."""
        window = self.get_window()
        if window is None:
            return False
        allocation = self.get_allocation()
        if self._collapsed or not self._click_through:
            full_region = cairo.Region(cairo.RectangleInt(0, 0, allocation.width, allocation.height))
            window.input_shape_combine_region(full_region, 0, 0)
            return False
        region = cairo.Region(
            control_region(PASSTHROUGH_CONTROL, allocation.width, allocation.height)
        )
        for center in (PIN_CONTROL, RESIZE_CONTROL, COLLAPSE_CONTROL):
            region.union(cairo.Region(control_region(center, allocation.width, allocation.height)))
        region.union(
            cairo.Region(
                control_region((120, 48), allocation.width, allocation.height, 73, 15)
            )
        )
        if self._view_mode == "usage":
            provider_region = control_region(
                PROVIDER_TOGGLE,
                allocation.width,
                allocation.height,
                24,
                11,
            )
            region.union(cairo.Region(provider_region))
        else:
            attention_region = control_region(
                ATTENTION_BUTTON_CENTER,
                allocation.width,
                allocation.height,
                21,
                21,
            )
            region.union(cairo.Region(attention_region))
        window.input_shape_combine_region(region, 0, 0)
        return False

    def _restore_position(self) -> None:
        position_file = POSITION_FILE if POSITION_FILE.is_file() else LEGACY_POSITION_FILE
        try:
            position = json.loads(position_file.read_text(encoding="utf-8"))
            self._widget_size = clamp_widget_size(position.get("size", WIDGET_SIZE))
            self._pinned = bool(position.get("pinned", True))
            self._click_through = bool(position.get("click_through", False))
            self._collapsed = bool(position.get("collapsed", False))
            saved_mode = position.get("view_mode", "usage")
            self._view_mode = saved_mode if saved_mode in {"usage", "overview", "attention"} else "usage"
            if isinstance(position.get("expanded_x"), int) and isinstance(position.get("expanded_y"), int):
                self._expanded_position = (position["expanded_x"], position["expanded_y"])
            self._apply_window_layer()
            if self._collapsed:
                self._apply_collapsed_geometry((int(position["x"]), int(position["y"])))
                self._sync_collapse_menu_label()
                return
            self.resize(self._widget_size, widget_height(self._widget_size))
            safe_x, safe_y = clamp_window_position(
                int(position["x"]),
                int(position["y"]),
                self._widget_size,
                widget_height(self._widget_size),
                self._monitor_workareas(),
            )
            self.move(safe_x, safe_y)
        except (OSError, ValueError, KeyError, TypeError):
            self.move(24, 24)

    def _save_position(self, position: Optional[tuple[int, int]] = None) -> None:
        try:
            self._position_file.parent.mkdir(parents=True, exist_ok=True)
            x, y = position or self.get_position()
            state = {
                "x": x,
                "y": y,
                "size": self._widget_size,
                "pinned": self._pinned,
                "click_through": self._click_through,
                "view_mode": self._view_mode,
                "collapsed": self._collapsed,
            }
            if self._expanded_position is not None:
                state["expanded_x"], state["expanded_y"] = self._expanded_position
            self._position_file.write_text(json.dumps(state), encoding="utf-8")
        except OSError:
            pass

    def refresh(self, force: bool = False) -> None:
        if self._refreshing and not force:
            return
        self._refresh_generation += 1
        generation = self._refresh_generation
        home = self._profiles[self._profile_index]["home"]
        self._refreshing = True
        threading.Thread(target=self._load_limits, args=(home, generation), daemon=True).start()

    def _load_limits(self, home: str, generation: int) -> None:
        try:
            results: list[Optional[list[UsageLimit]]] = [None, None]
            workers = [
                threading.Thread(
                    target=self._collect_source,
                    args=(lambda: read_codex_limits(home), results, 0),
                    daemon=True,
                ),
                threading.Thread(
                    target=self._collect_source,
                    args=(read_antigravity_limits, results, 1),
                    daemon=True,
                ),
            ]
            for worker in workers:
                worker.start()
            deadline = time.monotonic() + 40
            for worker in workers:
                worker.join(max(0, deadline - time.monotonic()))
            limits = [item for result in results if result for item in result]
            if not limits:
                if any(worker.is_alive() for worker in workers):
                    raise TimeoutError("Timed out while loading usage limits")
                raise ValueError("No usage limits available")
            GLib.idle_add(self._finish_refresh, generation, limits, False)
        except PROVIDER_ERRORS:
            GLib.idle_add(self._finish_refresh, generation, [], True)

    def _collect_source(self, source: Any, results: list[Optional[list[UsageLimit]]], index: int) -> None:
        try:
            results[index] = source()
        except PROVIDER_ERRORS as e:
            import traceback
            import subprocess
            err_msg = f"Source {index} failed with exception: {e}\n{traceback.format_exc()}"
            if isinstance(e, subprocess.TimeoutExpired):
                err_msg += f"\nStdout: {e.stdout}\nStderr: {e.stderr}"
            log_debug(err_msg)
            results[index] = None

    def _finish_refresh(self, generation: int, limits: list[UsageLimit], error: bool) -> bool:
        log_debug(f"Finish refresh: error={error}, limits={[(l.provider, l.name, l.used_percent) for l in limits]}")
        if generation != self._refresh_generation:
            return False
        self._refreshing = False
        self._error = error
        if not error:
            if any(item.remaining_percent <= 20 for item in limits):
                notify("Usage Limit", "Uma janela de uso está com 20% ou menos restante.")
            self._render_limits(limits)
        else:
            self._all_limits = []
            self._limits = []
            self._active_provider = None
            self._selected_limit = 0
            self._critical_phase = False
            self.area.queue_draw()
        return False

    def _scheduled_refresh(self) -> bool:
        self.refresh()
        return True

    def refresh_tasks(self) -> None:
        if self._task_refreshing:
            return
        self._task_refreshing = True
        source = self._task_source
        threading.Thread(target=self._load_tasks, args=(source,), daemon=True).start()

    def _load_tasks(self, source: CodexTaskSource) -> None:
        try:
            tasks = source.read()
            GLib.idle_add(self._finish_task_refresh, source, tasks, False)
        except PROVIDER_ERRORS:
            GLib.idle_add(self._finish_task_refresh, source, [], True)

    def _finish_task_refresh(
        self,
        source: CodexTaskSource,
        tasks: list[MonitoredTask],
        error: bool,
    ) -> bool:
        if source is not self._task_source:
            return False
        self._task_refreshing = False
        previous_signature = task_visual_signature(self._tasks)
        changed = error != self._task_error
        self._task_error = error
        if not error:
            unread_tasks = unread_task_transitions(self._known_task_statuses, tasks)
            approval_tasks, approval_task_ids = approval_task_transitions(
                self._known_approval_task_ids,
                tasks,
            )
            self._known_task_statuses.update({task.id: task.status for task in tasks})
            self._known_approval_task_ids = approval_task_ids
            self._tasks = tasks
            publish_approval_notifications(approval_tasks)
            if self._task_statuses_initialized:
                self._publish_lockscreen(unread_tasks)
            self._task_statuses_initialized = True
            changed = changed or previous_signature != task_visual_signature(tasks)
            shown = visible_tasks(tasks, self._view_mode)
            self._selected_task = min(self._selected_task, max(0, len(shown) - 1))
        else:
            self._tasks = []
            self._selected_task = 0
        if self._view_mode != "usage" and changed:
            self.area.queue_draw()
        if self._attention_window is not None and changed:
            self._attention_window.update_tasks(self._tasks, self._dark_mode)
        return False

    def _scheduled_task_refresh(self) -> bool:
        self.refresh_tasks()
        return True

    def close(self) -> None:
        if self._attention_window is not None:
            self._attention_window.destroy()
        self._task_source.close()
        self._ensure_visible()
        self._save_position()
        self.destroy()


def main() -> None:
    if Gtk is None or Gio is None or cairo is None:
        raise SystemExit("GTK is unavailable; install python3-gi and gir1.2-gtk-3.0.")
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    instance_lock = LOCK_FILE.open("w")
    try:
        fcntl.flock(instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    GLib.set_prgname("usage-limit")
    Gdk.set_program_class("usage-limit")
    Gtk.Window.set_default_icon_name("usage-limit")
    application = Gtk.Application(
        application_id="io.github.mehiel.UsageLimit",
        flags=Gio.ApplicationFlags.FLAGS_NONE,
    )

    def activate(app: Any) -> None:
        windows = app.get_windows()
        widget = windows[0] if windows else UsageLimitWidget(app)
        widget.show_all()
        widget.present()

    application.connect("activate", activate)
    application.run(None)


if __name__ == "__main__":
    main()
