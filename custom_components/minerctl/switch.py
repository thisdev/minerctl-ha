"""Schalter: Mining an/aus. (Board-Schalter: siehe Hinweis unten.)"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .entity import ConfigEntity


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    co = entry.runtime_data
    # Einzel-Board-Schalter (BoardSwitch) werden bewusst NICHT angelegt: Abschalten per
    # [hash_chain.N] enabled = false wirkt auf dem S9 nicht (verifiziert, siehe README).
    # Klasse bleibt für spätere Firmware/Modelle erhalten, falls es dort doch greift.
    add([MiningSwitch(co)])


class MiningSwitch(ConfigEntity, SwitchEntity):
    _attr_name = "Mining"
    _attr_icon = "mdi:pickaxe"

    def __init__(self, co) -> None:
        super().__init__(co, "mining")

    @property
    def is_on(self) -> bool:
        return bool(self.data.get("online")) or self.coordinator.busy is not None

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.run_change("Mining starten", self.coordinator.client.start)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.run_change("Mining stoppen", self.coordinator.client.stop)


class BoardSwitch(ConfigEntity, SwitchEntity):
    _attr_icon = "mdi:expansion-card"

    def __init__(self, co, cid: int) -> None:
        super().__init__(co, f"board_{cid}")
        self.cid = cid
        self._attr_name = f"Board {cid}"

    @property
    def is_on(self):
        return (self.cfg.get("chains") or {}).get(self.cid)

    async def async_turn_on(self, **kwargs) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set(False)

    async def _set(self, on: bool) -> None:
        if self.is_on == on:
            return
        await self.coordinator.run_change(f"Board {self.cid} {'an' if on else 'aus'}",
                                          lambda: self.coordinator.client.set_boards({self.cid: on}))
