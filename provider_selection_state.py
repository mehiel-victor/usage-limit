#!/usr/bin/env python3
"""Provider selection behavior shared by the usage widget."""

from __future__ import annotations

from usage_sources import SUPPORTED_PROVIDERS
from widget_support import log_debug


class ProviderSelectionState:
    def _toggle_provider(self) -> None:
        providers = {limit.provider for limit in self._all_limits}
        log_debug(
            f"Toggle provider: all_limits={[(l.provider, l.name) for l in self._all_limits]}, providers={providers}"
        )
        available = [provider for provider in SUPPORTED_PROVIDERS if provider in providers]
        if len(available) < 2:
            return
        current_index = available.index(self._active_provider)
        self._active_provider = available[(current_index + 1) % len(available)]
        self._limits = [limit for limit in self._all_limits if limit.provider == self._active_provider]
        self._selected_limit = min(self._selected_limit, max(0, len(self._limits) - 1))
        log_debug(
            f"Switched provider to: {self._active_provider}, new limits length: {len(self._limits)}"
        )
        self.area.queue_draw()
