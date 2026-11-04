#!/usr/bin/env python3
"""Cairo rendering and hit-testing for the circular Codex task view."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Optional

try:
    import cairo
except ImportError:
    cairo = None  # type: ignore[assignment]

try:
    import gi

    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo
except (ImportError, ValueError):
    Pango = PangoCairo = None  # type: ignore[assignment]

from task_sources import ATTENTION_STATUSES, MonitoredTask
from usage_limit_view import adaptive_text_color, theme_colors

BASE_WIDTH = 240
BASE_HEIGHT = 360
MODE_TOGGLE_RECT = (49, 28, 142, 26)
RING_CENTER = (120, 176)
RING_RADIUS = 106
RING_WIDTH = 20
ATTENTION_BUTTON_CENTER = (194, 90)

STATUS_COLORS = {
    "running": "#1473E6",
    "waiting_for_user": "#F59E0B",
    "blocked": "#EF4444",
    "failed": "#EF4444",
    "completed": "#62A47B",
    "queued": "#8290A8",
}
STATUS_LABELS = {
    "running": "executando",
    "waiting_for_user": "aguarda você",
    "blocked": "bloqueada",
    "failed": "falhou",
    "completed": "concluída",
    "queued": "na fila",
}
TRANSPARENT_TEXT = "#757575"


def visible_tasks(tasks: list[MonitoredTask], mode: str) -> list[MonitoredTask]:
    if mode == "attention":
        return [task for task in tasks if task.status in ATTENTION_STATUSES]
    return tasks


def _set_color(context: Any, color: str, alpha: float = 1.0) -> None:
    red, green, blue = (int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    context.set_source_rgba(red, green, blue, alpha)


def _rounded_rect(context: Any, x: float, y: float, width: float, height: float, radius: float) -> None:
    radius = min(radius, width / 2, height / 2)
    context.new_path()
    context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    context.arc(x + radius, y + radius, radius, math.pi, math.pi * 1.5)
    context.close_path()


def _text(
    context: Any,
    value: str,
    x: float,
    y: float,
    font: str,
    color: str,
    background_color: Optional[str] = None,
    width: Optional[int] = None,
) -> None:
    layout = PangoCairo.create_layout(context)
    layout.set_font_description(Pango.FontDescription(font))
    layout.set_text(value, -1)
    if width is not None:
        layout.set_width(width * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
    pixel_width, pixel_height = layout.get_pixel_size()
    context.move_to(x - pixel_width / 2, y - pixel_height / 2)
    effective_color = color if background_color is None else adaptive_text_color(color, background_color)
    _set_color(context, effective_color)
    PangoCairo.show_layout(context, layout)


def draw_mode_toggle(context: Any, mode: str, hovered: Optional[str], dark_mode: bool) -> None:
    x, y, width, height = MODE_TOGGLE_RECT
    palette = theme_colors(dark_mode)
    _rounded_rect(context, x, y, width, height, height / 2)
    _set_color(context, palette.control)
    context.fill()
    selected_mode = "usage" if mode == "usage" else "overview"
    labels = (("usage", "Limites"), ("overview", "Tarefas"))
    item_width = width / len(labels)
    for index, (value, _label) in enumerate(labels):
        left = x + index * item_width
        if selected_mode == value or hovered == f"mode:{value}":
            context.save()
            context.rectangle(left, y, item_width, height)
            context.clip()
            _rounded_rect(context, x, y, width, height, height / 2)
            fill = palette.control_active if selected_mode == value else palette.control_hover
            _set_color(context, fill)
            context.fill()
            context.restore()
    for index, (value, label) in enumerate(labels):
        left = x + index * item_width
        if selected_mode == value:
            label_background = palette.control_active
        elif hovered == f"mode:{value}":
            label_background = palette.control_hover
        else:
            label_background = palette.control
        _text(
            context,
            label,
            left + item_width / 2,
            y + height / 2,
            "Sans Bold 7",
            palette.primary if selected_mode == value else palette.secondary,
            background_color=label_background,
        )


def mode_at(x: float, y: float) -> Optional[str]:
    left, top, width, height = MODE_TOGGLE_RECT
    if not (left <= x <= left + width and top <= y <= top + height):
        return None
    modes = ("usage", "overview")
    index = min(len(modes) - 1, int((x - left) / (width / len(modes))))
    return modes[index]


def _stroke_arc(
    context: Any,
    color: str,
    width: float,
    start: float,
    end: float,
    alpha: float = 1.0,
    rounded: bool = True,
    radius: float = RING_RADIUS,
) -> None:
    context.new_path()
    context.set_line_cap(cairo.LINE_CAP_ROUND if rounded else cairo.LINE_CAP_BUTT)
    context.set_line_width(width)
    _set_color(context, color, alpha)
    context.arc(RING_CENTER[0], RING_CENTER[1], radius, start, end)
    context.stroke()


def _draw_ring(
    context: Any,
    tasks: list[MonitoredTask],
    selected: int,
    dark_mode: bool,
) -> None:
    palette = theme_colors(dark_mode)
    _stroke_arc(context, palette.control, RING_WIDTH, 0, math.tau, alpha=0.56, rounded=False)
    if not tasks:
        return
    segment = math.tau / len(tasks)
    start = -math.pi / 2
    for index, task in enumerate(tasks):
        segment_end = start + segment
        status_color = STATUS_COLORS.get(task.status, palette.tertiary)
        _stroke_arc(context, status_color, RING_WIDTH, start, segment_end)
        if index == selected:
            _stroke_arc(context, "#FFFFFF", RING_WIDTH - 4, start, segment_end, alpha=0.24)
        start += segment


def _draw_center(
    context: Any,
    all_tasks: list[MonitoredTask],
    shown_tasks: list[MonitoredTask],
    mode: str,
    dark_mode: bool,
) -> None:
    attention = sum(task.needs_attention for task in all_tasks)
    palette = theme_colors(dark_mode)
    if mode == "attention":
        main = f"{len(shown_tasks)} em atenção"
        detail = "ordenadas por prioridade"
    else:
        main = f"{len(all_tasks)} tarefas"
        detail = f"{attention} precisam de você"
    detail_color = "#D7DEE8" if dark_mode else "#374151"
    _text(context, main, 120, 168, "Sans Bold 15", palette.primary, palette.background, 174)
    _text(context, detail, 120, 190, "Sans Medium 8.5", detail_color, palette.background, 160)
    if any(task.status == "running" for task in all_tasks):
        context.new_path()
        _set_color(context, "#2F80ED")
        context.set_line_width(2.2)
        context.set_line_cap(cairo.LINE_CAP_ROUND)
        context.arc(120, 176, 57, math.pi * 0.15, math.pi * 0.78)
        context.stroke()


def _draw_attention_button(
    context: Any,
    attention_count: int,
    active: bool,
    hovered: bool,
    dark_mode: bool,
) -> None:
    x, y = ATTENTION_BUTTON_CENTER
    palette = theme_colors(dark_mode)
    tint = "#822F38" if active else palette.control
    context.new_path()
    _set_color(context, tint)
    context.arc(x, y, 18, 0, math.tau)
    context.fill()
    context.new_path()
    inactive = palette.control_hover if hovered else palette.control
    _set_color(context, "#E64D64" if active else inactive, 0.78)
    context.arc(x, y, 15, 0, math.tau)
    context.fill()
    icon = "#FFFFFF" if active else "#C8D0DC" if dark_mode else "#445064"
    _set_color(context, icon)
    context.set_line_width(2)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.move_to(x, y - 6)
    context.line_to(x, y + 1)
    context.stroke()
    context.new_path()
    context.arc(x, y + 6, 1.2, 0, math.tau)
    context.fill()
    if attention_count <= 0:
        return
    badge_x, badge_y = x + 12, y - 12
    context.new_path()
    _set_color(context, "#E33D43")
    context.arc(badge_x, badge_y, 8, 0, math.tau)
    context.fill()
    _text(context, str(attention_count), badge_x, badge_y, "Sans Bold 6.5", "#FFFFFF", "#E33D43")


def _draw_legend(context: Any, tasks: list[MonitoredTask], dark_mode: bool) -> None:
    counts = Counter(task.status for task in tasks)
    counts["failed"] += counts["blocked"]
    _text(
        context,
        f"{len(tasks)} tarefas monitoradas",
        120,
        302,
        "Sans Bold 7",
        TRANSPARENT_TEXT,
        width=180,
    )
    legend = (
        ("running", "executando"),
        ("waiting_for_user", "aguardando"),
        ("failed", "falhou"),
        ("completed", "concluída"),
        ("queued", "na fila"),
    )
    visible = [item for item in legend if counts.get(item[0], 0) > 0]
    if not visible:
        return
    if len(visible) <= 3:
        rows = [visible]
    elif len(visible) == 4:
        rows = [visible[:2], visible[2:]]
    else:
        rows = [visible[:3], visible[3:]]
    row_positions = (328,) if len(rows) == 1 else (316, 344)
    for row, center_y in zip(rows, row_positions):
        slot_width = 220 / len(row)
        for index, (status, label) in enumerate(row):
            center_x = 10 + slot_width * (index + 0.5)
            _set_color(context, STATUS_COLORS[status])
            context.new_path()
            context.arc(center_x - min(28, slot_width * 0.3), center_y, 4, 0, math.tau)
            context.fill()
            _text(
                context,
                f"{counts[status]} {label}",
                center_x + 8,
                center_y,
                "Sans Medium 7",
                TRANSPARENT_TEXT,
                width=max(45, round(slot_width - 22)),
            )


def draw_task_status(
    context: Any,
    tasks: list[MonitoredTask],
    mode: str,
    selected: int,
    hovered: Optional[str],
    error: bool,
    dark_mode: bool,
) -> None:
    context.set_antialias(cairo.ANTIALIAS_BEST)
    context.set_operator(cairo.OPERATOR_CLEAR)
    context.paint()
    context.set_operator(cairo.OPERATOR_OVER)
    shown = visible_tasks(tasks, mode)
    palette = theme_colors(dark_mode)
    context.new_path()
    _set_color(context, palette.background)
    context.arc(120, 176, 112, 0, math.tau)
    context.fill()
    draw_mode_toggle(context, mode, hovered, dark_mode)
    if error:
        palette = theme_colors(dark_mode)
        _text(context, "Sem acesso às tarefas", 120, 168, "Sans Bold 12", palette.primary, palette.background, 180)
        _text(context, "Clique para atualizar", 120, 190, "Sans 8", palette.secondary, palette.background)
    else:
        _draw_ring(context, shown, selected, dark_mode)
        _draw_center(context, tasks, shown, mode, dark_mode)
    _draw_attention_button(
        context,
        sum(task.needs_attention for task in tasks),
        mode == "attention",
        hovered == "attention-button",
        dark_mode,
    )
    _draw_legend(context, tasks, dark_mode)


def segment_at(x: float, y: float, task_count: int) -> Optional[int]:
    if task_count <= 0:
        return None
    center_x, center_y = RING_CENTER
    radius = math.hypot(x - center_x, y - center_y)
    if not (RING_RADIUS - RING_WIDTH <= radius <= RING_RADIUS + RING_WIDTH):
        return None
    angle = (math.atan2(y - center_y, x - center_x) + math.pi / 2) % math.tau
    return min(task_count - 1, int(angle / (math.tau / task_count)))


def attention_button_at(x: float, y: float) -> bool:
    return math.hypot(
        x - ATTENTION_BUTTON_CENTER[0],
        y - ATTENTION_BUTTON_CENTER[1],
    ) <= 20


def task_tooltip(task: MonitoredTask) -> str:
    source = "estado inferido" if task.status_source == "derived" else "estado nativo"
    label = STATUS_LABELS.get(task.status, task.status)
    return f"{task.title}\n{label} · {task.current_activity}\n{source}"
