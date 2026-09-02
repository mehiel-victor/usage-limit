#!/usr/bin/env python3
"""Window-state behavior for the compact right-edge usage dock."""

from __future__ import annotations

from typing import Optional

from collapsed_usage_view import COLLAPSED_HEIGHT, COLLAPSED_WIDTH, right_edge_position
from usage_limit_view import MIN_WIDGET_SIZE, clamp_window_position, widget_height

try:
    import gi

    gi.require_version("GLib", "2.0")
    from gi.repository import GLib
except (ImportError, ValueError):
    GLib = None  # type: ignore[assignment]


class CollapsedWindowState:
    """Manage geometry and restoration while a widget enters or leaves its dock."""

    def _toggle_collapsed(self) -> None:
        if self._collapsed:
            self._expand_from_provider(self._active_provider or "Codex")
            return
        x, y = self.get_position()
        width, height = self.get_size()
        self._expanded_position = (x, y)
        self._collapsed = True
        docked = self._apply_collapsed_geometry((x, y), (width, height))
        self._sync_collapse_menu_label()
        self._save_position(docked)

    def _expand_from_provider(self, provider: str) -> None:
        providers = {limit.provider for limit in self._all_limits}
        if provider in providers:
            self._active_provider = provider
            self._limits = [limit for limit in self._all_limits if limit.provider == provider]
            self._selected_limit = min(self._selected_limit, max(0, len(self._limits) - 1))
        self._collapsed = False
        self.set_skip_taskbar_hint(False)
        self.set_resizable(True)
        self.set_size_request(MIN_WIDGET_SIZE, widget_height(MIN_WIDGET_SIZE, self._view_mode))
        self.area.set_size_request(MIN_WIDGET_SIZE, widget_height(MIN_WIDGET_SIZE, self._view_mode))
        self.resize(self._widget_size, widget_height(self._widget_size, self._view_mode))
        if self._expanded_position is not None:
            self.move(*self._expanded_position)
        self.area.get_accessible().set_name("Limites de uso e status de tarefas")
        self._sync_collapse_menu_label()
        self._apply_window_layer()
        GLib.idle_add(self._apply_input_region)
        GLib.idle_add(self._ensure_visible)
        self.area.queue_draw()
        self._save_position(self._expanded_position)

    def _apply_collapsed_geometry(
        self,
        origin: tuple[int, int],
        origin_size: Optional[tuple[int, int]] = None,
    ) -> tuple[int, int]:
        width, height = origin_size or (COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        docked = right_edge_position(
            origin[0],
            origin[1],
            width,
            height,
            self._monitor_workareas(),
        )
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_size_request(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        self.area.set_size_request(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        self.resize(COLLAPSED_WIDTH, COLLAPSED_HEIGHT)
        self.move(*docked)
        self.area.get_accessible().set_name(
            "Limites recolhidos de Codex, Antigravity e Claude; pressione Enter para expandir"
        )
        self._apply_window_layer()
        GLib.idle_add(self._apply_input_region)
        self.area.queue_draw()
        return docked

    def _sync_collapse_menu_label(self) -> None:
        self._collapse_menu_item.set_label(
            "Expandir painel" if self._collapsed else "Recolher na borda"
        )

    def _remember_expanded_position_on_monitor(self, target_x: int, target_y: int) -> None:
        if not self._collapsed:
            return
        expanded_x = target_x + COLLAPSED_WIDTH - self._widget_size
        self._expanded_position = clamp_window_position(
            expanded_x,
            target_y,
            self._widget_size,
            widget_height(self._widget_size, self._view_mode),
            self._monitor_workareas(),
        )
