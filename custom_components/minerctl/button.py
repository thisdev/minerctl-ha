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
    add([ApplyButton(co), DiscardButton(co), RestartButton(co), RestoreButton(co)])


class ApplyButton(ConfigEntity, ButtonEntity):
    """Übernimmt den von Slider/Preset gesetzten Zielwert (löst den einen Neustart aus)."""
    _attr_name = "Übernehmen"
    _attr_icon = "mdi:check-bold"

    def __init__(self, co) -> None:
        super().__init__(co, "apply")

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.pending_changes()) and not self.coordinator.busy

    async def async_press(self) -> None:
        changes = self.coordinator.pending_changes()
        if not changes:
            return
        parts = []
        if "power" in changes:
            parts.append(f"{changes['power']} W")
        if "temp_target" in changes:
            parts.append(f"{changes['temp_target']} °C")
        await self.coordinator.run_change("Übernehmen: " + ", ".join(parts),
                                          lambda: self.coordinator.client.apply_changes(**changes))
        self.coordinator.clear_pending()
        self.coordinator.async_update_listeners()


class DiscardButton(ConfigEntity, ButtonEntity):
    """Verwirft den gesetzten Zielwert ohne Änderung am Miner (kein Neustart)."""
    _attr_name = "Zielwert verwerfen"
    _attr_icon = "mdi:undo"

    def __init__(self, co) -> None:
        super().__init__(co, "discard")

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.pending_changes())

    async def async_press(self) -> None:
        self.coordinator.clear_pending()
        self.coordinator.async_update_listeners()


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
