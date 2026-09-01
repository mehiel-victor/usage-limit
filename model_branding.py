#!/usr/bin/env python3
"""Model-brand marks used as low-contrast usage-panel watermarks."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

try:
    import gi

    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf, GLib
except (ImportError, ValueError):
    GdkPixbuf = GLib = None  # type: ignore[assignment]

ASSET_ROOT = Path(__file__).with_name("assets")


def _load_mark(filename: str, size: int) -> Any:
    if GdkPixbuf is None:
        return None
    try:
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(
            str(ASSET_ROOT / filename), size, size, True
        )
    except GLib.Error:
        return None


MODEL_MARKS = {
    "openai": _load_mark("openai-symbol.svg", 224),
    "antigravity": _load_mark("antigravity-icon.png", 224),
}


def model_mark(model_name: str, provider: str) -> Optional[Any]:
    """Select the closest available brand mark for the displayed model."""
    normalized = model_name.lower()
    if "gpt" in normalized or "codex" in normalized:
        return MODEL_MARKS.get("openai")
    if provider == "Antigravity":
        return MODEL_MARKS.get("antigravity")
    return None
