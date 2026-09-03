#!/usr/bin/env python3
"""Read-only Git worktree snapshots for repositories used by Codex tasks."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorktreeSnapshot:
    path: str
    branch: str
    repository: str
    ahead_of_main: int
    behind_main: int
    dirty: bool
    main_ref: str
    error: str = ""

    @property
    def unpublished(self) -> bool:
        return self.ahead_of_main > 0


def _git(path: str, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", path, *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=4,
    )
    return result.stdout.strip()


def _repository_root(path: str) -> str:
    try:
        return _git(path, "rev-parse", "--show-toplevel")
    except (OSError, subprocess.SubprocessError):
        return ""


def _main_ref(repository: str) -> str:
    for ref in ("origin/main", "upstream/main", "main"):
        try:
            _git(repository, "rev-parse", "--verify", ref)
            return ref
        except (OSError, subprocess.SubprocessError):
            continue
    return ""


def _worktree_rows(repository: str) -> list[tuple[str, str]]:
    output = _git(repository, "worktree", "list", "--porcelain")
    rows: list[tuple[str, str]] = []
    path = ""
    branch = "(detached)"
    for line in output.splitlines() + [""]:
        if line.startswith("worktree "):
            path = line.removeprefix("worktree ")
        elif line.startswith("branch "):
            branch = line.removeprefix("branch refs/heads/")
        elif not line and path:
            rows.append((path, branch))
            path, branch = "", "(detached)"
    return rows


def _snapshot(repository: str, path: str, branch: str) -> WorktreeSnapshot:
    main_ref = _main_ref(repository)
    ahead = behind = 0
    error = ""
    if main_ref and branch != "(detached)":
        try:
            counts = _git(path, "rev-list", "--left-right", "--count", f"{main_ref}...HEAD")
            behind, ahead = (int(value) for value in counts.split())
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            error = str(exc)
    elif not main_ref:
        error = "main remoto indisponível"
    try:
        dirty = bool(_git(path, "status", "--porcelain", "--untracked-files=no"))
    except (OSError, subprocess.SubprocessError):
        dirty = False
    return WorktreeSnapshot(path, branch, Path(repository).name, ahead, behind, dirty, main_ref, error)


def read_worktrees(paths: list[str]) -> list[WorktreeSnapshot]:
    repositories = {_repository_root(path) for path in paths if path}
    snapshots: list[WorktreeSnapshot] = []
    for repository in sorted(repositories):
        if not repository:
            continue
        try:
            rows = _worktree_rows(repository)
        except (OSError, subprocess.SubprocessError):
            continue
        snapshots.extend(_snapshot(repository, path, branch) for path, branch in rows)
    return sorted(snapshots, key=lambda item: (not item.unpublished, item.branch.lower()))


def worktree_paths(tasks: list[object]) -> list[str]:
    return [str(getattr(task, "cwd", "")) for task in tasks if getattr(task, "cwd", "")]
