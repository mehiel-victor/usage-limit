#!/usr/bin/env python3
"""Bridge Claude Code status-line JSON into Usage Limit's local state."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

STATE_FILE = Path(
    os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
) / "usage-limit" / "claude.json"


def _percentage(window: Any) -> str:
    if not isinstance(window, dict) or not isinstance(window.get("used_percentage"), (int, float)):
        return "—"
    return f"{window['used_percentage']:.0f}%"


def main() -> None:
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict):
        return
    rate_limits = payload.get("rate_limits")
    if not isinstance(rate_limits, dict):
        return
    state = {"updated_at": int(time.time()), "rate_limits": rate_limits}
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=STATE_FILE.parent,
        prefix=".claude-",
        delete=False,
    ) as stream:
        json.dump(state, stream)
        temporary = Path(stream.name)
    temporary.replace(STATE_FILE)
    five_hour = _percentage(rate_limits.get("five_hour"))
    seven_day = _percentage(rate_limits.get("seven_day"))
    print(f"Claude · 5h {five_hour} · 7d {seven_day}")


if __name__ == "__main__":
    main()
