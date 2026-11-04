#!/usr/bin/env python3
"""Install the opt-in panel entry and login startup, preserving user edits."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

APP_DIR = Path(__file__).resolve().parent


def install_entries(data_home: Path, config_home: Path) -> list[Path]:
    launcher = str(APP_DIR / "launch-usage-limit-panel")
    quoted = launcher.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    content = ("[Desktop Entry]\nType=Application\nName=Usage Limit · Barra do GNOME\n"
               "Comment=Limites restantes de Codex, Antigravity, Claude e Argon\n"
               f'Exec="{quoted}"\nIcon=utilities-system-monitor-symbolic\n'
               "Terminal=false\nCategories=Utility;\nX-GNOME-Autostart-enabled=true\n")
    state_path = data_home / "usage-limit/panel-install-state.json"
    previous = json.loads(state_path.read_text()) if state_path.exists() else {"files": {}}
    targets = [data_home / "applications/io.github.mehiel.UsageLimit.Panel.desktop",
               config_home / "autostart/io.github.mehiel.UsageLimit.Panel.desktop"]
    desired = content.encode()
    checksum = hashlib.sha256(desired).hexdigest()
    for target in targets:
        if target.exists():
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual not in {checksum, previous["files"].get(str(target), {}).get("sha256")}:
                raise ValueError(f"Arquivo alterado pelo usuário preservado: {target}")
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != desired:
            target.write_bytes(desired)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"files": {str(path): {"sha256": checksum} for path in targets}}, indent=2) + "\n")
    return targets


if __name__ == "__main__":
    subprocess.run([str(APP_DIR / "launch-usage-limit-panel"), "--check"], check=True)
    for entry in install_entries(Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))),
                                 Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))):
        print(f"Instalado: {entry}")
    print("Inicie com apps/usage-limit/launch-usage-limit-panel; o próximo login iniciará automaticamente.")
