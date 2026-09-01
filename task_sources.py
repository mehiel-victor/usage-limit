#!/usr/bin/env python3
"""Normalized status snapshots for recent local Codex tasks."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from usage_sources import codex_executable, read_codex_app_server

TASK_LIMIT = 10
ATTENTION_STATUSES = frozenset({"waiting_for_user", "blocked", "failed"})
STATUS_PRIORITY = {
    "waiting_for_user": 0,
    "blocked": 1,
    "failed": 1,
    "running": 4,
    "queued": 5,
    "completed": 6,
}


@dataclass(frozen=True)
class MonitoredTask:
    id: str
    title: str
    status: str
    status_source: str
    current_activity: str
    updated_at: int
    cwd: str = ""
    attention_kind: Optional[str] = None

    @property
    def needs_attention(self) -> bool:
        return self.status in ATTENTION_STATUSES


def _parse_timestamp(value: Any) -> int:
    if not isinstance(value, str):
        return 0
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return 0


def _tail_json(path: Path, max_bytes: int = 384 * 1024) -> list[dict[str, Any]]:
    try:
        with path.open("rb") as stream:
            size = stream.seek(0, os.SEEK_END)
            stream.seek(max(0, size - max_bytes))
            if size > max_bytes:
                stream.readline()
            return [
                item
                for line in stream
                if (item := _decode_json(line)) is not None
            ]
    except OSError:
        return []


def _decode_json(line: bytes) -> Optional[dict[str, Any]]:
    try:
        value = json.loads(line)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _event_details(events: list[dict[str, Any]]) -> tuple[str, str, int]:
    lifecycle = "queued"
    activity = "Na fila"
    updated_at = 0
    unresolved_calls: set[str] = set()
    for event in events:
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        updated_at = max(updated_at, _parse_timestamp(event.get("timestamp")))
        payload_type = payload.get("type")
        lifecycle, activity = _apply_lifecycle(payload_type, payload, lifecycle, activity)
        call_id = payload.get("call_id")
        if payload_type in {"custom_tool_call", "function_call"} and isinstance(call_id, str):
            if payload.get("name") in {"request_user_input", "tool_request_user_input"}:
                unresolved_calls.add(call_id)
        if payload_type in {"custom_tool_call_output", "function_call_output"} and isinstance(call_id, str):
            unresolved_calls.discard(call_id)
    if unresolved_calls:
        return "waiting_for_user", "Aguardando sua resposta", updated_at
    return lifecycle, activity, updated_at


def _apply_lifecycle(
    payload_type: Any,
    payload: dict[str, Any],
    status: str,
    activity: str,
) -> tuple[str, str]:
    if payload_type == "task_started":
        return "running", "Executando tarefa"
    if payload_type == "task_complete":
        return "completed", "Concluída"
    if payload_type == "turn_aborted":
        return "failed", "Execução interrompida"
    if payload_type != "item_completed":
        return status, activity
    item = payload.get("item")
    if not isinstance(item, dict):
        return status, activity
    item_type = item.get("type")
    if item.get("status") == "failed":
        return "failed", "Falha na atividade mais recente"
    labels = {
        "CommandExecution": "Executando comando",
        "McpToolCall": "Consultando integração",
        "FileChange": "Aplicando alterações",
        "AgentMessage": "Preparando resposta",
        "Reasoning": "Analisando",
    }
    next_activity = labels.get(str(item_type), activity)
    next_status = "running" if status == "failed" and str(item_type) in labels else status
    return next_status, next_activity


def _native_status(thread: dict[str, Any]) -> Optional[tuple[str, str, Optional[str]]]:
    raw_status = thread.get("status")
    if not isinstance(raw_status, dict):
        return None
    status_type = raw_status.get("type")
    flags = raw_status.get("activeFlags", [])
    if status_type == "systemError":
        return "failed", "Falha no processo do Codex", None
    if status_type == "active" and "waitingOnApproval" in flags:
        return "waiting_for_user", "Aguardando sua aprovação", "approval"
    if status_type == "active" and "waitingOnUserInput" in flags:
        return "waiting_for_user", "Aguardando sua resposta", "user_input"
    if status_type == "active":
        return "running", "Executando tarefa", None
    return None


RolloutCache = dict[str, tuple[int, int, tuple[str, str, int]]]


def _cached_event_details(path: Path, cache: RolloutCache) -> tuple[str, str, int]:
    path_key = str(path)
    try:
        stat = path.stat()
    except OSError:
        return "queued", "Na fila", 0
    cached = cache.get(path_key)
    if cached is not None and cached[:2] == (stat.st_mtime_ns, stat.st_size):
        return cached[2]
    details = _event_details(_tail_json(path))
    cache[path_key] = (stat.st_mtime_ns, stat.st_size, details)
    return details


def _normalize_thread(thread: dict[str, Any], cache: RolloutCache) -> MonitoredTask:
    path = Path(str(thread.get("path") or ""))
    derived_status, activity, event_time = _cached_event_details(path, cache)
    native = _native_status(thread)
    status, source = (native[0], "native") if native else (derived_status, "derived")
    if native:
        activity = native[1]
    elif status == "queued" and event_time >= int(time.time()) - 30:
        status = "running"
    title = str(thread.get("name") or thread.get("preview") or "Tarefa sem título")
    updated_at = max(int(thread.get("updatedAt") or 0), event_time)
    return MonitoredTask(
        id=str(thread.get("id") or ""),
        title=" ".join(title.split()),
        status=status,
        status_source=source,
        current_activity=activity,
        updated_at=updated_at,
        cwd=str(thread.get("cwd") or ""),
        attention_kind=native[2] if native else None,
    )


def _thread_list_params(limit: int) -> dict[str, Any]:
    return {
        "limit": limit,
        "archived": False,
        "sortKey": "recency_at",
        "sortDirection": "desc",
        "useStateDbOnly": True,
    }


def _tasks_from_result(
    result: dict[str, Any],
    cache: RolloutCache,
) -> list[MonitoredTask]:
    rows = result.get("data")
    if not isinstance(rows, list):
        raise ValueError("Codex returned no thread list")
    valid_rows = [row for row in rows if isinstance(row, dict) and row.get("id")]
    active_paths = {str(row.get("path") or "") for row in valid_rows}
    for path in tuple(cache):
        if path not in active_paths:
            cache.pop(path)
    tasks = [_normalize_thread(row, cache) for row in valid_rows]
    return sorted(tasks, key=lambda task: (STATUS_PRIORITY.get(task.status, 99), -task.updated_at))


class CodexTaskSource:
    """Reuse one app-server process and unchanged rollout snapshots."""

    def __init__(self, home: str = "") -> None:
        self._home = home
        self._process: Optional[subprocess.Popen[bytes]] = None
        self._buffer = b""
        self._request_id = 1
        self._rollout_cache: RolloutCache = {}

    def read(self, limit: int = TASK_LIMIT) -> list[MonitoredTask]:
        result = self._request("thread/list", _thread_list_params(limit))
        return _tasks_from_result(result, self._rollout_cache)

    def _request(self, method: str, params: Any) -> dict[str, Any]:
        try:
            self._ensure_process()
            self._request_id += 1
            request_id = self._request_id
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            return self._read_response(request_id)
        except (OSError, RuntimeError, TimeoutError, ValueError):
            self.close()
            raise

    def _ensure_process(self) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        environment = os.environ.copy()
        if self._home:
            environment["CODEX_HOME"] = self._home
        process = subprocess.Popen(
            [codex_executable(), "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=environment,
        )
        if process.stdin is None or process.stdout is None:
            process.terminate()
            raise OSError("Could not start the Codex app server")
        self._process = process
        self._buffer = b""
        self._send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"clientInfo": {"name": "usage-limit", "version": "1.0"}},
            }
        )
        self._read_response(1)
        self._send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

    def _send(self, message: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.stdin is None:
            raise OSError("Codex app server is not running")
        process.stdin.write((json.dumps(message) + "\n").encode())
        process.stdin.flush()

    def _read_response(self, request_id: int, timeout: float = 10) -> dict[str, Any]:
        process = self._process
        if process is None or process.stdout is None:
            raise OSError("Codex app server is not running")
        deadline = time.monotonic() + timeout
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            while time.monotonic() < deadline:
                response = self._consume_response(request_id)
                if response is not None:
                    return response
                events = selector.select(max(0, deadline - time.monotonic()))
                if not events:
                    break
                chunk = process.stdout.read1(65_536)
                if not chunk:
                    raise OSError("Codex app server closed its output")
                self._buffer += chunk
        raise TimeoutError("Timed out while reading Codex tasks")

    def _consume_response(self, request_id: int) -> Optional[dict[str, Any]]:
        while b"\n" in self._buffer:
            line, self._buffer = self._buffer.split(b"\n", 1)
            decoded = _decode_json(line)
            if decoded is None or decoded.get("id") != request_id:
                continue
            if decoded.get("error") is not None:
                raise RuntimeError(str(decoded["error"]))
            result = decoded.get("result")
            if not isinstance(result, dict):
                raise ValueError("Codex returned invalid task data")
            return result
        return None

    def close(self) -> None:
        process, self._process = self._process, None
        self._buffer = b""
        if process is None or process.poll() is not None:
            return
        process.terminate()
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=0.5)


def read_codex_tasks(home: str = "", limit: int = TASK_LIMIT) -> list[MonitoredTask]:
    result = read_codex_app_server("thread/list", _thread_list_params(limit), home)
    return _tasks_from_result(result, {})


def open_codex_task(task_id: str) -> None:
    """Open a local Codex task using the desktop application's public deep link."""
    subprocess.Popen(
        ["xdg-open", f"codex://threads/{task_id}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
