#!/usr/bin/env python3
"""Notifications and diagnostics shared by the usage-limit widget."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime

from task_sources import MonitoredTask
from usage_sources import UsageLimit

UNREAD_TRIGGER_STATUSES = frozenset({"waiting_for_user", "blocked", "failed", "completed"})


def notify_lockscreen(message: str, replace_id: int = 0) -> int:
    """Publish a resident notification and return its server identifier."""
    executable = shutil.which("notify-send")
    if not executable:
        return 0
    command = [
        executable,
        "--print-id",
        "--app-name=Usage Limit",
        "--hint", "boolean:resident:true",
        "--hint", "string:desktop-entry:io.github.mehiel.UsageLimit",
        "--urgency=normal",
    ]
    if replace_id:
        command.extend(("--replace-id", str(replace_id)))
    result = subprocess.run(
        [*command, "Chats não lidos", message],
        check=False,
        capture_output=True,
        text=True,
        timeout=3,
    )
    try:
        return int(result.stdout.strip())
    except ValueError:
        return 0


def format_lockscreen_status(limits: list[UsageLimit], tasks: list[MonitoredTask]) -> str:
    """Build a concise notification containing limits and unread tasks."""
    usage = " · ".join(
        f"{limit.provider}: {limit.remaining_percent}%"
        for limit in limits[:2]
    ) or "Limites indisponíveis"
    if not tasks:
        return f"{usage}\nNenhum chat não lido"
    lines = [f"• {task.title} ({task.current_activity})" for task in tasks[:5]]
    if len(tasks) > 5:
        lines.append(f"(+{len(tasks) - 5} outros)")
    return f"{usage}\n" + "\n".join(lines)


def unread_task_transitions(
    previous_statuses: dict[str, str],
    tasks: list[MonitoredTask],
) -> list[MonitoredTask]:
    """Return tasks that just entered a status requiring the user's attention."""
    return [
        task
        for task in tasks
        if task.status in UNREAD_TRIGGER_STATUSES
        and previous_statuses.get(task.id) != task.status
    ]


def log_debug(message: str) -> None:
    if os.environ.get("USAGE_LIMIT_DEBUG") != "1":
        return
    try:
        with open("/tmp/usage_limit_debug.log", "a", encoding="utf-8") as stream:
            stream.write(f"{datetime.now().isoformat()} - {message}\n")
    except OSError:
        pass
