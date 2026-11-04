"""Logo and status-colored text for Ubuntu's rectangular AppIndicator support."""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path

import cairo

from usage_limit_view import usage_color

ASSETS = Path(__file__).resolve().parent / "assets"
MARKS = {"codex": "panel-openai.png", "gemini": "panel-antigravity.png",
         "claude": "panel-claude.png", "argon": "panel-argon.png"}
CACHE = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "usage-limit/panel-status-v1"


def text_color(remaining: int | None) -> tuple[float, ...]:
    color = usage_color(remaining) if remaining is not None else "#B3BAC7"
    return tuple(int(color[index:index + 2], 16) / 255 for index in (1, 3, 5))


def draw_logo(context: cairo.Context, key: str, size: float) -> None:
    logo = cairo.ImageSurface.create_from_png(str(ASSETS / MARKS[key]))
    scale = size / max(logo.get_width(), logo.get_height())
    context.save()
    context.translate((size - logo.get_width() * scale) / 2,
                      (size - logo.get_height() * scale) / 2)
    context.scale(scale, scale)
    context.set_source_surface(logo, 0, 0)
    if key == "codex":
        mask = context.get_source()
        context.set_source_rgb(0.96, 0.97, 1)
        context.mask(mask)
    else:
        context.paint()
    context.restore()


def render_status(key: str, text: str, remaining: int | None) -> cairo.ImageSurface:
    """Render at panel height: no progress track and no markup in native labels."""
    if remaining is not None and not 0 <= remaining <= 100:
        raise ValueError("Remaining quota must be between 0 and 100")
    measure = cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1))
    measure.select_font_face("Ubuntu Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    measure.set_font_size(12.5)
    options = cairo.FontOptions()
    options.set_antialias(cairo.ANTIALIAS_GRAY)
    measure.set_font_options(options)
    extents = measure.text_extents(text)
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, math.ceil(26 + extents.x_advance), 20)
    context = cairo.Context(surface)
    context.save()
    context.translate(1, 2)
    draw_logo(context, key, 16)
    context.restore()
    context.set_scaled_font(measure.get_scaled_font())
    context.set_source_rgb(*text_color(remaining))
    context.move_to(24, (20 - extents.height) / 2 - extents.y_bearing)
    context.show_text(text)
    return surface


def status_icon(key: str, text: str, remaining: int | None, cache: Path = CACHE) -> Path:
    digest = hashlib.sha256(text.encode()).hexdigest()[:10]
    target = cache / f"{key}-{remaining}-{digest}.png"
    if not target.exists():
        cache.mkdir(parents=True, exist_ok=True)
        render_status(key, text, remaining).write_to_png(str(target))
    return target
