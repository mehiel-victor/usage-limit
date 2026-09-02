#!/usr/bin/env python3
"""Diagnostics shared by the usage-limit widget."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from task_sources import MonitoredTask


def task_visual_signature(
    tasks: list[MonitoredTask],
) -> tuple[tuple[str, str, str, str, Optional[str]], ...]:
    return tuple(
        (task.id, task.title, task.status, task.current_activity, task.attention_kind)
        for task in tasks
    )


def log_debug(message: str) -> None:
    if os.environ.get("USAGE_LIMIT_DEBUG") != "1":
        return
    try:
        with open("/tmp/usage_limit_debug.log", "a", encoding="utf-8") as stream:
            stream.write(f"{datetime.now().isoformat()} - {message}\n")
    except OSError:
        pass
