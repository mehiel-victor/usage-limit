"""Summaries of real quota windows for the GNOME panel."""
from __future__ import annotations

from dataclasses import dataclass

from usage_sources import UsageLimit


@dataclass(frozen=True)
class PanelGroup:
    key: str
    label: str
    title: str


GROUPS = (
    PanelGroup("codex", "Codex", "ChatGPT · Codex"),
    PanelGroup("gemini", "Gemini", "Antigravity · Gemini"),
    PanelGroup("claude", "Claude", "Antigravity · Claude e GPT (cota compartilhada)"),
    PanelGroup("argon", "Argon", "Antigravity · Gemini 4 Argon"),
)


def group_limits(limits: list[UsageLimit]) -> dict[str, list[UsageLimit]]:
    groups: dict[str, list[UsageLimit]] = {group.key: [] for group in GROUPS}
    for limit in limits:
        name = limit.name.casefold()
        if limit.provider == "Codex":
            key = "codex"
        elif limit.provider != "Antigravity":
            continue
        elif "argon" in name:
            key = "argon"
        elif "claude" in name or "gpt" in name:
            key = "claude"
        elif "gemini" in name:
            key = "gemini"
        else:
            continue
        groups[key].append(limit)
    return groups


def remaining_percent(windows: list[UsageLimit]) -> int | None:
    return min(item.remaining_percent for item in windows) if windows else None


def group_label(_group: PanelGroup, windows: list[UsageLimit]) -> str:
    remaining = remaining_percent(windows)
    return f"{remaining}%" if remaining is not None else "—"
