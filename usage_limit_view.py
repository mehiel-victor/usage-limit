#!/usr/bin/env python3
"""Cairo primitives and rendering support for the usage-limit view."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
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

MONTHS_PT_BR = ("jan.", "fev.", "mar.", "abr.", "mai.", "jun.", "jul.", "ago.", "set.", "out.", "nov.", "dez.")
WIDGET_SIZE = 240
WIDGET_HEIGHT = 380
CONTENT_OFFSET_Y = 68
MIN_WIDGET_SIZE = 180
MAX_WIDGET_SIZE = 360
PROVIDER_TOGGLE = (120, 347)
PASSTHROUGH_CONTROL = (80, 15)
PIN_CONTROL = (120, 15)
RESIZE_CONTROL = (160, 15)
CONTROL_RADIUS = 13


@dataclass(frozen=True)
class ThemeColors:
    background: str
    alternate_background: str
    track: str
    primary: str
    secondary: str
    tertiary: str
    label: str
    alternate_label: str
    dot_active: str
    dot_inactive: str
    control: str
    control_hover: str
    control_active: str
    control_active_hover: str
    icon: str
    active_icon: str


def theme_colors(dark_mode: bool) -> ThemeColors:
    if dark_mode:
        return ThemeColors(
            "#121212", "#1C191E", "#2C2C2C", "#F7F9FC", "#B8C0CD", "#8E98A7", "#8FB6D0", "#B9B2C0",
            "#D8DEE8", "#4B5361", "#242424", "#333333", "#2B3C30", "#354A3B", "#AAB3C1", "#81C995",
        )
    return ThemeColors(
        "#F7F7F5", "#F0EFF2", "#D9DDD9", "#202124", "#4F5551", "#676D69", "#456C84", "#635E68",
        "#343936", "#AEB5B0", "#ECEEEC", "#DEE2DF", "#DDEEE1", "#D0E7D5", "#555D58", "#4E9B61",
    )


def critical_colors(colors: ThemeColors) -> ThemeColors:
    return ThemeColors(
        colors.background,
        colors.alternate_background,
        "#70434A",
        colors.primary,
        colors.secondary,
        colors.tertiary,
        colors.label,
        colors.alternate_label,
        "#FFD2DA",
        "#8F626B",
        "#5B3038",
        "#70404A",
        "#8B435C",
        "#FFD8E0",
        colors.icon,
        "#FFD0D9",
    )


def system_prefers_dark(color_scheme: str, gtk_theme: str = "", gtk_prefers_dark: bool = False) -> bool:
    if color_scheme == "prefer-light":
        return False
    if color_scheme == "prefer-dark":
        return True
    return gtk_prefers_dark or "dark" in gtk_theme.lower()


def format_reset_date(timestamp: Optional[int]) -> str:
    if timestamp is None:
        return "Renovação indisponível"
    date = datetime.fromtimestamp(timestamp).astimezone()
    return f"Renova em {date.day} de {MONTHS_PT_BR[date.month - 1]}"


def _set_color(context: Any, color: str, alpha: float = 1.0) -> None:
    red, green, blue = (int(color[index : index + 2], 16) / 255 for index in (1, 3, 5))
    context.set_source_rgba(red, green, blue, alpha)


def _rounded_rectangle(
    context: Any,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
) -> None:
    radius = min(radius, width / 2, height / 2)
    context.new_path()
    context.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    context.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    context.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    context.arc(x + radius, y + radius, radius, math.pi, math.pi * 1.5)
    context.close_path()


def _is_dark_theme(colors: ThemeColors) -> bool:
    red, green, blue = (int(colors.background[index : index + 2], 16) for index in (1, 3, 5))
    return red * 0.299 + green * 0.587 + blue * 0.114 < 128


def _draw_text(
    context: Any,
    text: str,
    center_y: float,
    font: str,
    color: str,
    max_width: Optional[int] = None,
    center_x: Optional[float] = None,
) -> None:
    layout = PangoCairo.create_layout(context)
    layout.set_font_description(Pango.FontDescription(font))
    layout.set_text(text, -1)
    if max_width is not None:
        layout.set_width(max_width * Pango.SCALE)
        layout.set_ellipsize(Pango.EllipsizeMode.END)
    width, height = layout.get_pixel_size()
    context.move_to((center_x if center_x is not None else WIDGET_SIZE / 2) - width / 2, center_y - height / 2)
    _set_color(context, color)
    PangoCairo.show_layout(context, layout)


def usage_level(remaining_percent: int) -> str:
    if remaining_percent >= 60:
        return "high"
    if remaining_percent >= 30:
        return "medium"
    return "low"


def usage_color(remaining_percent: int) -> str:
    colors = {
        "high": "#62D093",
        "medium": "#FFB340",
        "low": "#FF5F65",
    }
    return colors[usage_level(remaining_percent)]


def _draw_usage_ring(context: Any, remaining_percent: int, colors: ThemeColors, critical: bool = False) -> None:
    center, radius = WIDGET_SIZE / 2, 106
    context.set_line_width(20)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    _set_color(context, colors.track, 0.58)
    context.arc(center, center, radius, 0, math.tau)
    context.stroke()
    fraction = max(0.0, min(1.0, remaining_percent / 100))
    if fraction == 0:
        return
    _set_color(context, "#FF5F65" if critical else usage_color(remaining_percent))
    context.arc(center, center, radius, -math.pi / 2, -math.pi / 2 + math.tau * fraction)
    context.stroke()


def control_at(x: float, y: float) -> Optional[str]:
    if abs(x - PROVIDER_TOGGLE[0]) <= 24 and abs(y - PROVIDER_TOGGLE[1]) <= 11:
        return "provider"
    for name, center in (("passthrough", PASSTHROUGH_CONTROL), ("pin", PIN_CONTROL), ("resize", RESIZE_CONTROL)):
        if math.hypot(x - center[0], y - center[1]) <= CONTROL_RADIUS:
            return name
    return None


def clamp_widget_size(size: float) -> int:
    return max(MIN_WIDGET_SIZE, min(MAX_WIDGET_SIZE, round(size)))


def widget_height(width: float) -> int:
    return round(width * WIDGET_HEIGHT / WIDGET_SIZE)


def outward_resize_delta(delta_x: float, delta_y: float) -> float:
    circle_center = (WIDGET_SIZE / 2, CONTENT_OFFSET_Y + WIDGET_SIZE / 2)
    outward_x = RESIZE_CONTROL[0] - circle_center[0]
    outward_y = RESIZE_CONTROL[1] - circle_center[1]
    distance = math.hypot(outward_x, outward_y)
    return (delta_x * outward_x + delta_y * outward_y) / distance


def control_region(
    center: tuple[int, int],
    width: int,
    height: int,
    half_width: int = CONTROL_RADIUS + 2,
    half_height: Optional[int] = None,
) -> cairo.RectangleInt:
    scale = min(width / WIDGET_SIZE, height / WIDGET_HEIGHT)
    scaled_height = (half_height if half_height is not None else half_width) * scale
    scaled_width = half_width * scale
    center_x, center_y = center[0] * scale, center[1] * scale
    return cairo.RectangleInt(
        max(0, round(center_x - scaled_width)),
        max(0, round(center_y - scaled_height)),
        max(1, round(scaled_width * 2)),
        max(1, round(scaled_height * 2)),
    )


def clamp_window_position(
    x: int,
    y: int,
    width: int,
    height: int,
    workareas: list[tuple[int, int, int, int]],
    pointer: Optional[tuple[int, int]] = None,
) -> tuple[int, int]:
    valid_areas = [area for area in workareas if area[2] > 0 and area[3] > 0]
    if not valid_areas:
        return x, y
    target = next(
        (
            area
            for area in valid_areas
            if pointer
            and area[0] <= pointer[0] < area[0] + area[2]
            and area[1] <= pointer[1] < area[1] + area[3]
        ),
        None,
    )
    if target is None:
        def overlap(area: tuple[int, int, int, int]) -> int:
            area_x, area_y, area_width, area_height = area
            overlap_width = max(0, min(x + width, area_x + area_width) - max(x, area_x))
            overlap_height = max(0, min(y + height, area_y + area_height) - max(y, area_y))
            return overlap_width * overlap_height
        target = max(valid_areas, key=overlap)
    area_x, area_y, area_width, area_height = target
    safe_x = max(area_x, min(x, area_x + max(0, area_width - width)))
    safe_y = max(area_y, min(y, area_y + max(0, area_height - height)))
    return safe_x, safe_y


def _draw_icon_control(
    context: Any,
    name: str,
    center: tuple[int, int],
    active: bool,
    hovered: bool,
    colors: ThemeColors,
) -> None:
    x, y = center
    tint = colors.control_active if active else colors.control_hover if hovered else colors.control
    context.new_path()
    _set_color(context, tint)
    context.arc(x, y, 11, 0, math.tau)
    context.fill()
    _set_color(context, colors.active_icon if active else colors.icon)
    context.set_line_width(1.45)
    context.set_line_cap(cairo.LINE_CAP_ROUND)
    context.set_line_join(cairo.LINE_JOIN_ROUND)
    if name == "passthrough":
        context.move_to(x - 5, y - 6)
        context.line_to(x + 4.5, y + 1)
        context.line_to(x + 0.5, y + 1.8)
        context.line_to(x + 3, y + 6)
        context.line_to(x + 0.5, y + 7)
        context.line_to(x - 1.8, y + 2.8)
        context.line_to(x - 4.5, y + 5)
        context.close_path()
    elif name == "pin":
        context.move_to(x - 4.5, y - 5)
        context.line_to(x + 4.5, y - 5)
        context.move_to(x - 2.7, y - 4.5)
        context.line_to(x - 1.8, y)
        context.line_to(x - 4.5, y + 3)
        context.line_to(x + 4.5, y + 3)
        context.line_to(x + 1.8, y)
        context.line_to(x + 2.7, y - 4.5)
        context.move_to(x, y + 3)
        context.line_to(x, y + 7)
    else:
        context.move_to(x - 5, y + 5)
        context.line_to(x + 5, y - 5)
        context.move_to(x + 1, y - 5)
        context.line_to(x + 5, y - 5)
        context.line_to(x + 5, y - 1)
        context.move_to(x - 1, y + 5)
        context.line_to(x - 5, y + 5)
        context.line_to(x - 5, y + 1)
    context.stroke()


def _draw_utility_controls(
    context: Any,
    pinned: bool,
    click_through: bool,
    hovered: Optional[str],
    colors: ThemeColors,
) -> None:
    _draw_icon_control(context, "passthrough", PASSTHROUGH_CONTROL, click_through, hovered == "passthrough", colors)
    _draw_icon_control(context, "pin", PIN_CONTROL, pinned, hovered == "pin", colors)
    _draw_icon_control(context, "resize", RESIZE_CONTROL, False, hovered == "resize", colors)


def _draw_controls(
    context: Any,
    pinned: bool,
    click_through: bool,
    hovered: Optional[str],
    colors: ThemeColors,
    active_provider: Optional[str],
    available_providers: set[str],
) -> None:
    toggle_x, toggle_y = PROVIDER_TOGGLE
    toggle_hovered = hovered == "provider" and len(available_providers) > 1
    _rounded_rectangle(context, toggle_x - 23, toggle_y - 10, 46, 20, 10)
    _set_color(context, colors.control_hover if toggle_hovered else colors.control)
    context.fill()
    for index, provider in enumerate(("Codex", "Antigravity")):
        left = toggle_x - 22 + index * 22
        active, enabled = provider == active_provider, provider in available_providers
        if active and enabled:
            _rounded_rectangle(context, left, toggle_y - 9, 22, 18, 8)
            _set_color(context, colors.control_active)
            context.fill()
        color = colors.primary if active and enabled else colors.icon if enabled else colors.tertiary
        _draw_text(context, "C" if index == 0 else "A", toggle_y, "Sans Bold 8", color, center_x=left + 11)
    _draw_utility_controls(context, pinned, click_through, hovered, colors)
