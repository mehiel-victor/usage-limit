#!/usr/bin/env python3
"""Compact right-edge rendering for provider usage limits."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from usage_limit_view import _draw_text, _rounded_rectangle, _set_color, theme_colors, usage_color
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

COLLAPSED_WIDTH = 86
COLLAPSED_HEIGHT = 218
CAPSULE_X = 8
CAPSULE_WIDTH = COLLAPSED_WIDTH - CAPSULE_X
CAPSULE_HEIGHT = 66
CAPSULE_GAP = 6
CAPSULE_TOPS = tuple(4 + index * (CAPSULE_HEIGHT + CAPSULE_GAP) for index in range(len(SUPPORTED_PROVIDERS)))
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
        "Codex": _load_logo("openai-symbol.svg", 23),
        "Antigravity": _load_logo("antigravity-icon.png", 25),
        "Claude Code": _load_logo("panel-claude.png", 23),
    }
else:
    PROVIDER_LOGOS = {}


def provider_at(x: float, y: float) -> Optional[str]:
    """Return the provider represented by the capsule under a point."""
    if not CAPSULE_X <= x <= COLLAPSED_WIDTH:
        return None
    for provider, top in zip(PROVIDERS, CAPSULE_TOPS):
        if top <= y <= top + CAPSULE_HEIGHT:
            return provider
    return None


def provider_remaining(limits: list[Any], provider: str) -> Optional[int]:
    """Use the provider's primary displayed window in the compact dock."""
    limit = next((item for item in limits if item.provider == provider), None)
    return limit.remaining_percent if limit is not None else None


def right_edge_position(
    x: int,
    y: int,
    width: int,
    height: int,
    workareas: list[tuple[int, int, int, int]],
) -> tuple[int, int]:
    """Dock a compact window to the right edge of its current monitor."""
    valid_areas = [area for area in workareas if area[2] > 0 and area[3] > 0]
    if not valid_areas:
        return x, y

    def overlap(area: tuple[int, int, int, int]) -> int:
        area_x, area_y, area_width, area_height = area
        overlap_width = max(0, min(x + width, area_x + area_width) - max(x, area_x))
        overlap_height = max(0, min(y + height, area_y + area_height) - max(y, area_y))
        return overlap_width * overlap_height

    area_x, area_y, area_width, area_height = max(valid_areas, key=overlap)
    docked_x = area_x + area_width - COLLAPSED_WIDTH
    docked_y = max(area_y, min(y, area_y + area_height - COLLAPSED_HEIGHT))
    return docked_x, docked_y


def _draw_logo(context: Any, provider: str, center_y: float) -> None:
    context.new_path()
    _set_color(context, "#F7F9FC")
    context.arc(33, center_y, 17, 0, 6.283185307179586)
    context.fill()
    logo = PROVIDER_LOGOS.get(provider)
    if logo is None or Gdk is None:
        _draw_text(
            context,
            provider[0],
            center_y,
            "Sans Bold 11",
            "#202124",
            background_color="#F7F9FC",
            center_x=33,
        )
        return
    context.save()
    Gdk.cairo_set_source_pixbuf(
        context,
        logo,
        33 - logo.get_width() / 2,
        center_y - logo.get_height() / 2,
    )
    context.paint()
    context.restore()


def _draw_usage_bar(context: Any, remaining: Optional[int], top: int, colors: Any) -> None:
    track_x, track_y, track_width, track_height = 68, top + 12, 8, 42
    _rounded_rectangle(context, track_x, track_y, track_width, track_height, 4)
    _set_color(context, colors.track, 0.75)
    context.fill()
    if remaining is None or remaining <= 0:
        return
    fill_height = max(4, track_height * remaining / 100)
    _rounded_rectangle(
        context,
        track_x,
        track_y + track_height - fill_height,
        track_width,
        fill_height,
        4,
    )
    _set_color(context, usage_color(remaining))
    context.fill()


def draw_collapsed_widget(
    context: Any,
    limits: list[Any],
    hovered_provider: Optional[str],
    dark_mode: bool,
) -> None:
    """Render two provider ellipses with logos and rounded usage bars."""
    colors = theme_colors(dark_mode)
    context.set_operator(cairo.OPERATOR_CLEAR)
    context.paint()
    context.set_operator(cairo.OPERATOR_OVER)
    for provider, top in zip(PROVIDERS, CAPSULE_TOPS):
        remaining = provider_remaining(limits, provider)
        _rounded_rectangle(
            context,
            CAPSULE_X,
            top,
            CAPSULE_WIDTH,
            CAPSULE_HEIGHT,
            CAPSULE_HEIGHT / 2,
        )
        _set_color(context, colors.control_hover if hovered_provider == provider else colors.background, 0.97)
        context.fill()
        _draw_logo(context, provider, top + 25)
        _draw_usage_bar(context, remaining, top, colors)
        _draw_text(
            context,
            "—" if remaining is None else f"{remaining}%",
            top + 51,
            "Sans Bold 7",
            colors.primary if remaining is not None else colors.tertiary,
            background_color=colors.background,
            center_x=33,
        )
