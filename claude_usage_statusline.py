#!/usr/bin/env python3
"""Bridge Claude Code's status-line JSON to a private, quota-only local snapshot."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

from usage_sources import CLAUDE_STATE_FILE, CLAUDE_WINDOWS, parse_claude_limits


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (ValueError, UnicodeError):
        return
    if not isinstance(payload, dict):
        return
    if not isinstance(payload.get("rate_limits"), dict):
        # An unsupported/new session must not retain a previous account's quota.
        try:
            CLAUDE_STATE_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        print("Claude Code · limites indisponíveis")
        return
    limits = parse_claude_limits(payload)
    keys = {label: key for key, label in CLAUDE_WINDOWS.items()}
    windows = {}
    for limit in limits:
        window = {"used_percentage": limit.used_percent}
        if limit.resets_at is not None:
            window["resets_at"] = limit.resets_at
        windows[keys[limit.window]] = window
    state = {"updated_at": int(time.time()), "rate_limits": windows}
    temporary = None
    try:
        CLAUDE_STATE_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                         dir=CLAUDE_STATE_FILE.parent, prefix=".claude-",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(state, stream, allow_nan=False)
        os.replace(temporary, CLAUDE_STATE_FILE)
    except OSError:
        print("Claude Code · limites indisponíveis")
        return
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    summary = " · ".join(f"{limit.window} {limit.remaining_percent}% restante" for limit in limits)
    print(f"Claude Code · {summary or 'limites indisponíveis'}")


if __name__ == "__main__":
    main()
