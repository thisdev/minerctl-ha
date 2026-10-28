"""Tasten: bosminer neu starten, Original-Config wiederherstellen."""
from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .entity import ConfigEntity


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    co = entry.runtime_data
    add([RestartButton(co), RestoreButton(co)])


class RestartButton(ConfigEntity, ButtonEntity):
    _attr_name = "Mining neu starten"
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, co) -> None:
        super().__init__(co, "restart")

    async def async_press(self) -> None:
        await self.coordinator.run_change("Neustart", self.coordinator.client.restart)


class RestoreButton(ConfigEntity, ButtonEntity):
    _attr_name = "Original-Config wiederherstellen"
    _attr_icon = "mdi:backup-restore"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False   # bewusst versteckt, im Gerät aktivierbar

    def __init__(self, co) -> None:
        super().__init__(co, "restore")

    async def async_press(self) -> None:
        await self.coordinator.run_change("Original-Config", self.coordinator.client.restore)
