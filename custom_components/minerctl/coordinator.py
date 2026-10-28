"""Datenabruf und zentrale Ausführung von Änderungen."""
from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import BosMiner, MinerError
from .const import CONF_SCAN_INTERVAL, CONFIG_REFRESH, DEFAULT_PRESETS, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class MinerCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: BosMiner) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN} {entry.title}",
                         update_interval=timedelta(seconds=interval))
        self.entry = entry
        self.client = client
        self.busy: Optional[str] = None          # z. B. "Preset Medium" während einer Änderung
        self.last_error: Optional[str] = None
        self._cfg: Optional[dict] = None
        self._cfg_time = 0.0
        self.version: dict = {}
        self.pending_power: Optional[int] = None   # von Slider/Preset gesetzter Zielwert, erst per "Übernehmen" aktiv
        self.pending_temp: Optional[float] = None  # gesetzte Zieltemperatur, erst per "Übernehmen" aktiv

    @property
    def presets(self) -> Dict[str, dict]:
        presets = {k: dict(v) for k, v in DEFAULT_PRESETS.items()}
        for key, val in (self.entry.options.get("presets") or {}).items():
            if key in presets:
                presets[key].update(val)
        return presets

    async def _async_update_data(self) -> Dict[str, Any]:
        data = await self.client.fetch_api()
        if self._cfg is None or time.monotonic() - self._cfg_time > CONFIG_REFRESH:
            try:
                self._cfg = await self.client.config_state()
                self._cfg_time = time.monotonic()
                data.pop("config_error", None)
            except MinerError as err:
                data["config_error"] = str(err)
        if not data["online"] and self._cfg is None:
            raise UpdateFailed(data.get("config_error") or data.get("api_error") or "Miner nicht erreichbar")
        if not data["online"] and "config_error" not in data:
            data["stopped"] = True
        data["config"] = self._cfg
        if (self.pending_power is not None and self._cfg
                and self._cfg.get("power_limit") == self.pending_power and self._cfg.get("autotuning")):
            self.pending_power = None   # Leistungs-Zielwert ist jetzt aktiv
        if self.pending_temp is not None and self._cfg and self._cfg.get("temp_target") == self.pending_temp:
            self.pending_temp = None    # Temperatur-Zielwert ist jetzt aktiv
        return data

    async def run_change(self, label: str, action: Callable[[], Awaitable[Any]]) -> Any:
        """Änderung ausführen: Zustand 'busy' anzeigen, Fehler als HA-Fehler melden, danach neu einlesen."""
        if self.client.change_lock.locked():
            raise HomeAssistantError(f"Es läuft noch eine Änderung ({self.busy}). Bitte kurz warten.")
        self.busy = label
        self.last_error = None
        self.async_update_listeners()
        try:
            return await action()
        except MinerError as err:
            self.last_error = str(err)
            raise HomeAssistantError(f"{label}: {err}") from err
        finally:
            self.busy = None
            self._cfg = None             # Config sofort neu lesen
            await self.async_request_refresh()

    def current_preset(self) -> Optional[str]:
        cfg = (self.data or {}).get("config")
        if not cfg or not cfg.get("autotuning"):
            return None
        for key, p in self.presets.items():
            if p["power"] == cfg["power_limit"]:
                return key
        return None

    def pending_changes(self) -> Dict[str, Any]:
        """Noch nicht übernommene Zielwerte (leer = nichts zu übernehmen)."""
        cfg = (self.data or {}).get("config") or {}
        out: Dict[str, Any] = {}
        if (self.pending_power is not None
                and not (cfg.get("power_limit") == self.pending_power and cfg.get("autotuning"))):
            out["power"] = self.pending_power
        if self.pending_temp is not None and cfg.get("temp_target") != self.pending_temp:
            out["temp_target"] = self.pending_temp
        return out

    def clear_pending(self) -> None:
        self.pending_power = None
        self.pending_temp = None
