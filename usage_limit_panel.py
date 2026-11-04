#!/usr/bin/env python3
"""GNOME/Ubuntu AppIndicator using the widget's existing read-only sources."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
import signal
import subprocess
import sys
import threading

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import AyatanaAppIndicator3, Gio, GLib, Gtk

from panel_icons import status_icon
from panel_model import GROUPS, group_label, group_limits, remaining_percent
from usage_sources import UsageLimit, configured_profiles, read_antigravity_limits, read_codex_limits

APP_DIR = Path(__file__).resolve().parent
WINDOW_NAMES = {"session": "Sessão", "weekly": "Semana", "5h": "5 horas", "usage": "Uso"}


def collect_limits() -> tuple[list[UsageLimit], set[str]]:
    """Keep provider failures independent and never expose exception payloads."""
    limits: list[UsageLimit] = []
    failed: set[str] = set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        codex = [(profile, pool.submit(read_codex_limits, profile["home"]))
                 for profile in configured_profiles()]
        antigravity = pool.submit(read_antigravity_limits)
        for profile, future in codex:
            try:
                for item in future.result():
                    name = f'{profile["name"]} · {item.name}' if len(codex) > 1 else item.name
                    limits.append(UsageLimit(item.provider, name, item.window, item.used_percent, item.resets_at))
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
                failed.add("Codex")
        try:
            limits.extend(antigravity.result())
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            failed.add("Antigravity")
    return limits, failed


class UsagePanel(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(application_id="io.github.mehiel.UsageLimit.Panel",
                         flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.indicators = {}
        self.busy = False
        self.timer = 0
        self.refresh_items = []

    def do_activate(self) -> None:
        if self.indicators:
            self.refresh()
            return
        self.hold()
        for index, group in enumerate(GROUPS):
            indicator = AyatanaAppIndicator3.Indicator.new(
                f"usage-limit-{group.key}", str(status_icon(group.key, group_label(group, []), None)),
                AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS)
            indicator.set_title(group.title)
            indicator.set_label("", "")
            indicator.set_ordering_index(100 + index)
            self.indicators[group.key] = indicator
        self.render([], set(), loading=True)
        for indicator in self.indicators.values():
            indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.refresh()
        self.timer = GLib.timeout_add_seconds(300, self.refresh)

    def refresh(self, *_args) -> bool:
        if not self.busy:
            self.busy = True
            for item in self.refresh_items:
                item.set_label("Atualizando…")
                item.set_sensitive(False)
            threading.Thread(target=self._collect, daemon=True).start()
        return GLib.SOURCE_CONTINUE

    def _collect(self) -> None:
        limits, failed = collect_limits()
        GLib.idle_add(self._updated, limits, failed)

    def _updated(self, limits: list[UsageLimit], failed: set[str]) -> bool:
        self.busy = False
        self.render(limits, failed)
        return GLib.SOURCE_REMOVE

    @staticmethod
    def add_action(menu: Gtk.Menu, icon: str, description: str, callback) -> Gtk.MenuItem:
        item = Gtk.ImageMenuItem()
        item.set_label(description)
        item.set_image(Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.LARGE_TOOLBAR))
        item.set_always_show_image(True)
        item.set_tooltip_text(description)
        item.get_accessible().set_name(description)
        item.connect("activate", callback)
        menu.append(item)
        return item

    @staticmethod
    def add_detail(menu: Gtk.Menu, text: str) -> None:
        item = Gtk.MenuItem.new_with_label(text)
        item.set_sensitive(False)
        menu.append(item)

    def render(self, limits: list[UsageLimit], failed: set[str], loading: bool = False) -> None:
        groups = group_limits(limits)
        self.refresh_items = []
        for group in GROUPS:
            windows = groups[group.key]
            description = [group.title]
            menu = Gtk.Menu()
            self.add_detail(menu, group.title)
            self.add_detail(menu, "Saldo restante")
            menu.append(Gtk.SeparatorMenuItem())
            if not windows:
                source = "Codex" if group.key == "codex" else "Antigravity"
                status = "Consultando…" if loading else "Falha na consulta; tente atualizar" if source in failed else "Cota não informada pelo serviço"
                description.append(status)
                self.add_detail(menu, status)
            for item in windows:
                window = WINDOW_NAMES.get(item.window, item.window)
                reset = datetime.fromtimestamp(item.resets_at).strftime("%d/%m às %H:%M") if item.resets_at else "não informado"
                description.append(f"{item.name} · {window}: {item.remaining_percent}% restante · renova {reset}")
                self.add_detail(menu, f"{window} · {item.remaining_percent}% disponível")
                self.add_detail(menu, f"Renova {reset}")
                if group.key == "codex" and len(configured_profiles()) > 1:
                    self.add_detail(menu, item.name)
            indicator = self.indicators[group.key]
            indicator.set_icon_full(str(status_icon(group.key, group_label(group, windows), remaining_percent(windows))), "\n".join(description))
            indicator.set_label("", "")
            menu.append(Gtk.SeparatorMenuItem())
            if not loading:
                self.add_detail(menu, f"Consulta às {datetime.now():%H:%M} · a cada 5 min")
            self.refresh_items.append(self.add_action(menu, "view-refresh-symbolic", "Atualizar agora", self.refresh))
            self.add_action(menu, "window-new-symbolic", "Abrir janela Usage Limit",
                            lambda *_: subprocess.Popen([str(APP_DIR / "launch-usage-limit")]))
            self.add_action(menu, "application-exit-symbolic", "Sair do indicador", lambda *_: self.quit())
            menu.show_all()
            old_menu = indicator.get_menu()
            indicator.set_menu(menu)
            if old_menu:
                old_menu.destroy()

    def do_shutdown(self) -> None:
        if self.timer:
            GLib.source_remove(self.timer)
        for indicator in self.indicators.values():
            indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.PASSIVE)
        Gtk.Application.do_shutdown(self)


if __name__ == "__main__":
    if "--check" in sys.argv:
        print("GTK 3 e Ayatana AppIndicator disponíveis")
        sys.exit(0)
    app = UsagePanel()
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: app.quit())
    app.run(None)
