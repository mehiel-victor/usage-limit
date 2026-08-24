#!/usr/bin/env python3
"""Rounded, clickable queue for active Codex tasks."""

from __future__ import annotations

import math
from typing import Any, Callable

import cairo
import gi

gi.require_version("Gdk", "3.0")
gi.require_version("Gtk", "3.0")
from gi.repository import Gdk, Gtk, Pango

from task_sources import ATTENTION_STATUSES, MonitoredTask
from task_status_view import STATUS_COLORS, STATUS_LABELS

WINDOW_SIZE = 360
QUEUE_STATUSES = ATTENTION_STATUSES | {"running", "queued"}
_STYLED_SCREENS: set[int] = set()
_CSS = b"""
window.codex-attention-window { background-color: transparent; }
.codex-attention-screen { background-color: #11151b; border: 1px solid #3b4658; border-radius: 18px; padding: 16px; }
.codex-attention-screen scrolledwindow, .codex-attention-screen viewport { background-color: transparent; }
.codex-attention-header { color: #f7f9fc; font-weight: 700; font-size: 15px; }
.codex-attention-count { background-color: #e33d43; color: #ffffff; border-radius: 11px; padding: 3px 8px; font-weight: 700; }
button.codex-attention-close, button.codex-attention-task { background: transparent; border: 0; box-shadow: none; }
button.codex-attention-close { color: #aab3c1; padding: 4px; border-radius: 12px; }
button.codex-attention-close:hover { background-color: #28313e; }
button.codex-attention-task { border-radius: 11px; padding: 9px; }
button.codex-attention-task:hover, button.codex-attention-task:focus { background-color: #202733; }
.codex-attention-title { color: #f2f4f8; font-weight: 600; }
.codex-attention-status, .codex-attention-empty { color: #9ea9ba; font-size: 10px; }
.codex-attention-empty { padding: 48px 16px; }
.codex-attention-screen.light { background-color: #f7f7f5; border-color: #c8ced6; }
.codex-attention-screen.light .codex-attention-header, .codex-attention-screen.light .codex-attention-title { color: #202124; }
.codex-attention-screen.light .codex-attention-status, .codex-attention-screen.light .codex-attention-empty { color: #596575; }
.codex-attention-screen.light button.codex-attention-task:hover, .codex-attention-screen.light button.codex-attention-task:focus { background-color: #e8ebef; }
"""


def _install_styles(screen: Any) -> None:
    screen_id = id(screen)
    if screen_id in _STYLED_SCREENS:
        return
    provider = Gtk.CssProvider()
    provider.load_from_data(_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        screen,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    _STYLED_SCREENS.add(screen_id)


def _status_dot(status: str, dark_mode: bool) -> Any:
    dot = Gtk.DrawingArea()
    dot.set_size_request(10, 10)
    dot.set_valign(Gtk.Align.CENTER)

    def draw(_widget: Any, context: Any) -> bool:
        rgba = Gdk.RGBA()
        rgba.parse(STATUS_COLORS.get(status, STATUS_COLORS["queued"]))
        rim = 1 if dark_mode else 0
        context.set_source_rgba(rim, rim, rim, 0.30 if dark_mode else 0.14)
        context.arc(5, 5, 5, 0, math.tau)
        context.fill()
        context.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)
        context.arc(5, 5, 3.8, 0, math.tau)
        context.fill()
        return False

    dot.connect("draw", draw)
    return dot


def _queue_tasks(tasks: list[MonitoredTask]) -> list[MonitoredTask]:
    return [task for task in tasks if task.status in QUEUE_STATUSES]


def _task_status_text(task: MonitoredTask) -> str:
    activity = task.current_activity.strip()
    return activity or STATUS_LABELS.get(task.status, task.status)


class AttentionQueueWindow(Gtk.Window):
    def __init__(
        self,
        parent: Any,
        tasks: list[MonitoredTask],
        dark_mode: bool,
        on_task_open: Callable[[str], None],
    ) -> None:
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self._on_task_open = on_task_open
        self._dark_mode = dark_mode
        self.set_application(parent.get_application())
        self.set_transient_for(parent)
        self.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
        self.set_title("Fila de tarefas do Codex")
        self.set_default_size(WINDOW_SIZE, WINDOW_SIZE)
        self.set_size_request(WINDOW_SIZE, WINDOW_SIZE)
        self.set_resizable(False)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.set_keep_above(True)
        self.set_app_paintable(True)
        visual = self.get_screen().get_rgba_visual()
        if visual is not None:
            self.set_visual(visual)
        self.get_style_context().add_class("codex-attention-window")
        self.connect("draw", self._clear_background)
        self.connect("key-press-event", self._on_key)
        self._content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(self._content)
        _install_styles(self.get_screen())
        self.update_tasks(tasks, dark_mode)

    def update_tasks(self, tasks: list[MonitoredTask], dark_mode: bool) -> None:
        self._dark_mode = dark_mode
        for child in self._content.get_children():
            self._content.remove(child)
        screen = self._build_screen(_queue_tasks(tasks), dark_mode)
        self._content.pack_start(screen, True, True, 0)
        if self.get_visible():
            self._content.show_all()

    def _build_screen(self, tasks: list[MonitoredTask], dark_mode: bool) -> Any:
        screen = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        screen.get_style_context().add_class("codex-attention-screen")
        if not dark_mode:
            screen.get_style_context().add_class("light")
        screen.pack_start(self._build_header(len(tasks)), False, False, 0)
        if not tasks:
            empty = Gtk.Label(label="Nenhuma tarefa ativa na fila")
            empty.get_style_context().add_class("codex-attention-empty")
            screen.pack_start(empty, True, True, 0)
            return screen
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        rows = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for task in tasks:
            rows.pack_start(self._task_button(task, dark_mode), False, False, 0)
        scroll.add(rows)
        screen.pack_start(scroll, True, True, 0)
        return screen

    def _build_header(self, count: int) -> Any:
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        title = Gtk.Label(label="Fila de tarefas", xalign=0)
        title.get_style_context().add_class("codex-attention-header")
        badge = Gtk.Label(label=str(count))
        badge.get_style_context().add_class("codex-attention-count")
        close = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.BUTTON)
        close.set_relief(Gtk.ReliefStyle.NONE)
        close.set_tooltip_text("Fechar")
        close.get_style_context().add_class("codex-attention-close")
        close.connect("clicked", lambda _button: self.destroy())
        header.pack_start(title, True, True, 0)
        header.pack_start(badge, False, False, 0)
        header.pack_end(close, False, False, 0)
        return header

    def _task_button(self, task: MonitoredTask, dark_mode: bool) -> Any:
        button = Gtk.Button()
        button.set_relief(Gtk.ReliefStyle.NONE)
        button.get_style_context().add_class("codex-attention-task")
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        row.pack_start(_status_dot(task.status, dark_mode), False, False, 0)
        labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label=task.title, xalign=0)
        title.set_ellipsize(Pango.EllipsizeMode.END)
        title.set_max_width_chars(38)
        title.get_style_context().add_class("codex-attention-title")
        status_text = _task_status_text(task)
        status = Gtk.Label(label=status_text, xalign=0)
        status.set_ellipsize(Pango.EllipsizeMode.END)
        status.get_style_context().add_class("codex-attention-status")
        labels.pack_start(title, False, False, 0)
        labels.pack_start(status, False, False, 0)
        row.pack_start(labels, True, True, 0)
        button.add(row)
        button.set_tooltip_text(f"{task.title}\n{status_text}")
        button.connect("clicked", lambda _button: self._open_task(task.id))
        return button

    def _open_task(self, task_id: str) -> None:
        self._on_task_open(task_id)
        self.destroy()

    def _clear_background(self, _widget: Any, context: Any) -> bool:
        context.set_operator(cairo.OPERATOR_CLEAR)
        context.paint()
        context.set_operator(cairo.OPERATOR_OVER)
        allocation = self.get_allocation()
        radius = 18
        x, y, width, height = 1, 1, allocation.width - 2, allocation.height - 2
        context.new_path()
        context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
        context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
        context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
        context.arc(x + radius, y + radius, radius, math.pi, math.pi * 1.5)
        context.close_path()
        if self._dark_mode:
            context.set_source_rgba(0.067, 0.082, 0.106, 0.98)
        else:
            context.set_source_rgba(0.969, 0.969, 0.961, 0.98)
        context.fill()
        return False

    def _on_key(self, _widget: Any, event: Any) -> bool:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()
            return True
        return False
