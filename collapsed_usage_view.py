#!/usr/bin/env python3
"""Left-edge provider capsules matching the compact reference layout."""

from __future__ import annotations

from pathlib import Path
import math
from typing import Any, Optional

from usage_limit_view import _draw_text, _rounded_rectangle, _set_color, usage_color
from usage_sources import SUPPORTED_PROVIDERS

try:
    import cairo
except ImportError:
    cairo = None  # type: ignore[assignment]

try:
    import gi

    gi.require_version("Gdk", "3.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, GLib
except (ImportError, ValueError):
    Gdk = GdkPixbuf = GLib = None  # type: ignore[assignment]

COLLAPSED_WIDTH = 96
CAPSULE_X = 0
CAPSULE_WIDTH = COLLAPSED_WIDTH - CAPSULE_X
CAPSULE_HEIGHT = 76
CAPSULE_GAP = 8
CAPSULE_TOPS = tuple(4 + index * (CAPSULE_HEIGHT + CAPSULE_GAP) for index in range(len(SUPPORTED_PROVIDERS)))
COLLAPSED_HEIGHT = CAPSULE_TOPS[-1] + CAPSULE_HEIGHT + 4
CAPSULE_COLOR = "#000000"
CAPSULE_HOVER_COLOR = "#121212"
LOGO_BACKGROUND = "#D3D3D3"
TRACK_COLOR = "#333333"
LOGO_CENTER_X = 58
LOGO_RADIUS = 27
LOGO_SIZE = 40
BAR_X, BAR_WIDTH, BAR_HEIGHT = 11, 10, 54
PROVIDERS = SUPPORTED_PROVIDERS
ASSET_ROOT = Path(__file__).with_name("assets")


def _load_logo(name: str, size: int) -> Any:
    if GdkPixbuf is None:
        return None
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(ASSET_ROOT / name),
            size,
            size,
            True,
        )
    except GLib.Error:  # type: ignore[name-defined]
        return None


if GdkPixbuf is not None:
    PROVIDER_LOGOS = {
        "Codex": _load_logo("openai-symbol.svg", LOGO_SIZE * 3),
        "Antigravity": _load_logo("antigravity-icon.png", LOGO_SIZE * 3),
        "Claude Code": _load_logo("panel-claude.png", LOGO_SIZE * 3),
    }
else:
    PROVIDER_LOGOS = {}


def provider_at(x: float, y: float) -> Optional[str]:
    """Return the provider represented by the capsule under a point."""
    if not CAPSULE_X <= x <= COLLAPSED_WIDTH:
        return None
    for provider, top in zip(PROVIDERS, CAPSULE_TOPS):
        radius = CAPSULE_HEIGHT / 2
        if top <= y <= top + CAPSULE_HEIGHT and (
            x <= LOGO_CENTER_X or (x - LOGO_CENTER_X) ** 2 + (y - top - radius) ** 2 <= radius ** 2
        ):
            return provider
    return None


def provider_remaining(limits: list[Any], provider: str) -> Optional[int]:
    """Use the provider's primary displayed window in the compact dock."""
    limit = next((item for item in limits if item.provider == provider), None)
    return limit.remaining_percent if limit is not None else None


def collapsed_accessible_label(limits: list[Any]) -> str:
    values = []
    for provider in PROVIDERS:
        remaining = provider_remaining(limits, provider)
        status = "indisponível" if remaining is None else f"{remaining}% restante"
        values.append(f"{provider}: {status}")
    return "Limites recolhidos. " + ". ".join(values) + ". Pressione Enter para expandir."


def left_edge_position(
    x: int,
    y: int,
    width: int,
    height: int,
    workareas: list[tuple[int, int, int, int]],
) -> tuple[int, int]:
    """Dock to the selected monitor's left workarea edge, including negative origins."""
    valid_areas = [area for area in workareas if area[2] > 0 and area[3] > 0]
    if not valid_areas:
        return x, y

    def overlap(area: tuple[int, int, int, int]) -> int:
        area_x, area_y, area_width, area_height = area
        overlap_width = max(0, min(x + width, area_x + area_width) - max(x, area_x))
        overlap_height = max(0, min(y + height, area_y + area_height) - max(y, area_y))
        return overlap_width * overlap_height

    area_x, area_y, area_width, area_height = max(
        valid_areas,
        key=lambda area: (overlap(area), area[0] <= x + width / 2 < area[0] + area[2]),
    )
    docked_x = area_x
    docked_y = max(area_y, min(y, area_y + area_height - COLLAPSED_HEIGHT))
    return docked_x, docked_y


def _draw_logo(context: Any, provider: str, center_y: float) -> None:
    context.new_path()
    _set_color(context, LOGO_BACKGROUND)
    context.arc(LOGO_CENTER_X, center_y, LOGO_RADIUS, 0, math.tau)
    context.fill()
    logo = PROVIDER_LOGOS.get(provider)
    if logo is None or Gdk is None:
        _draw_text(
            context,
            provider[0],
            center_y,
            "Sans Bold 11",
            "#202124",
            background_color=LOGO_BACKGROUND,
            center_x=LOGO_CENTER_X,
        )
        return
    context.save()
    scale = LOGO_SIZE / max(logo.get_width(), logo.get_height())
    context.translate(LOGO_CENTER_X - logo.get_width() * scale / 2,
                      center_y - logo.get_height() * scale / 2)
    context.scale(scale, scale)
    Gdk.cairo_set_source_pixbuf(context, logo, 0, 0)
    context.paint()
    context.restore()


def _draw_usage_bar(context: Any, remaining: Optional[int], top: int) -> None:
    track_y = top + (CAPSULE_HEIGHT - BAR_HEIGHT) / 2
    _rounded_rectangle(context, BAR_X, track_y, BAR_WIDTH, BAR_HEIGHT, BAR_WIDTH / 2)
    _set_color(context, TRACK_COLOR)
    context.fill()
    if remaining is None:
        _set_color(context, "#B3BAC7")
        context.set_line_width(2)
        context.move_to(BAR_X + 2, top + CAPSULE_HEIGHT / 2)
        context.line_to(BAR_X + BAR_WIDTH - 2, top + CAPSULE_HEIGHT / 2)
        context.stroke()
        return
    if remaining <= 0:
        return
    fill_height = max(4, BAR_HEIGHT * remaining / 100)
    _rounded_rectangle(
        context,
        BAR_X,
        track_y + BAR_HEIGHT - fill_height,
        BAR_WIDTH,
        fill_height,
        4,
    )
    _set_color(context, usage_color(remaining))
    context.fill()


def collapsed_input_region(width: int, height: int) -> Any:
    """Let the desktop receive clicks in the transparent gaps and rounded corners."""
    if width <= 0 or height <= 0:
        return cairo.Region()
    scale = min(width / COLLAPSED_WIDTH, height / COLLAPSED_HEIGHT)
    region = cairo.Region()
    radius = CAPSULE_HEIGHT / 2
    for row in range(height):
        y = (row + 0.5) / scale
        top = next((top for top in CAPSULE_TOPS if top <= y < top + CAPSULE_HEIGHT), None)
        if top is None:
            continue
        right = LOGO_CENTER_X + math.sqrt(max(0, radius ** 2 - (y - top - radius) ** 2))
        region.union(cairo.Region(cairo.RectangleInt(0, row, math.ceil(right * scale), 1)))
    return region


def draw_collapsed_widget(
    context: Any,
    limits: list[Any],
    hovered_provider: Optional[str],
    dark_mode: bool,
) -> None:
    """Render black D-shaped capsules, left quota bars, and gray-backed provider marks."""
    context.set_operator(cairo.OPERATOR_CLEAR)
    context.paint()
    context.set_operator(cairo.OPERATOR_OVER)
    for provider, top in zip(PROVIDERS, CAPSULE_TOPS):
        remaining = provider_remaining(limits, provider)
        radius = CAPSULE_HEIGHT / 2
        context.new_path()
        context.move_to(0, top)
        context.line_to(LOGO_CENTER_X, top)
        context.arc(LOGO_CENTER_X, top + radius, radius, -math.pi / 2, math.pi / 2)
        context.line_to(0, top + CAPSULE_HEIGHT)
        context.close_path()
        _set_color(context, CAPSULE_HOVER_COLOR if hovered_provider == provider else CAPSULE_COLOR)
        context.fill()
        _draw_logo(context, provider, top + radius)
        _draw_usage_bar(context, remaining, top)
