"""Leistungsgrenze als Schieberegler. Die Grenzen passen sich der Zahl laufender Boards an."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .const import POWER_STEP
from .entity import ConfigEntity

# Grenzen bei voller Bestückung (3 Boards); werden proportional zur erkannten Board-Zahl skaliert.
# ~130 W je Board unten (beobachteter Tuner-Floor ~380 W bei 3 Boards), ~473 W je Board oben.
FULL_BOARDS = 3
FULL_MIN_W = 390
FULL_MAX_W = 1420


def _board_count(d: dict) -> int:
    """Zahl der real gemeldeten Boards (aus der API). Rückfall: Config-Chains, sonst 3."""
    devs = [x for x in (d.get("devs") or []) if isinstance(x.get("ID"), int)]
    if devs:
        return len(devs)
    chains = (d.get("config") or {}).get("chains") or {}
    return len(chains) or FULL_BOARDS


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    add([PowerLimit(entry.runtime_data)])


class PowerLimit(ConfigEntity, NumberEntity):
    _attr_name = "Leistungsgrenze"
    _attr_icon = "mdi:flash"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_step = POWER_STEP
    _attr_mode = NumberMode.SLIDER

    def __init__(self, co) -> None:
        super().__init__(co, "power_limit")

    def _boards(self) -> int:
        return max(1, _board_count(self.data))

    @property
    def native_min_value(self) -> float:
        return round(FULL_MIN_W * self._boards() / FULL_BOARDS)

    @property
    def native_max_value(self) -> float:
        return round(FULL_MAX_W * self._boards() / FULL_BOARDS)

    @property
    def native_value(self):
        # Zeigt den gesetzten Zielwert, solange er noch nicht übernommen wurde, sonst den aktiven.
        p = self.coordinator.pending_power
        return p if p is not None else self.cfg.get("power_limit")

    @property
    def extra_state_attributes(self):
        return {
            "erkannte_boards": self._boards(),
            "aktiv_w": self.cfg.get("power_limit"),
            "uebernehmen_ausstehend": self.coordinator.pending_active() is not None,
        }

    async def async_set_native_value(self, value: float) -> None:
        # Startet den Miner NICHT neu – setzt nur den Zielwert. Übernahme über den Button "Übernehmen".
        self.coordinator.pending_power = int(round(value))
        self.coordinator.async_update_listeners()
