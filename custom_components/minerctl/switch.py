"""Schalter: Mining an/aus und einzelne Hashboards."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .entity import ConfigEntity


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    co = entry.runtime_data
    chains = ((co.data or {}).get("config") or {}).get("chains", {6: True, 7: True, 8: True})
    add([MiningSwitch(co)] + [BoardSwitch(co, cid) for cid in sorted(chains)])


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
