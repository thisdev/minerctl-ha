"""Preset-Auswahl (Minimum … Maximum)."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .entity import ConfigEntity

CUSTOM = "Eigene Einstellung"


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    add([PresetSelect(entry.runtime_data)])


class PresetSelect(ConfigEntity, SelectEntity):
    _attr_name = "Preset"
    _attr_icon = "mdi:tune-variant"

    def __init__(self, co) -> None:
        super().__init__(co, "preset")
        self._labels = {p["label"]: k for k, p in co.presets.items()}
        self._attr_options = list(self._labels) + [CUSTOM]

    @property
    def current_option(self):
        key = self.coordinator.current_preset()
        return self.coordinator.presets[key]["label"] if key else CUSTOM

    @property
    def extra_state_attributes(self):
        return {p["label"]: f"{p['power']} W" for p in self.coordinator.presets.values()}

    async def async_select_option(self, option: str) -> None:
        if option == CUSTOM:
            raise HomeAssistantError("'Eigene Einstellung' entsteht durch manuelle Änderungen und ist nicht wählbar.")
        preset = self.coordinator.presets[self._labels[option]]
        await self.coordinator.run_change(f"Preset {option}", lambda: self.coordinator.client.apply_preset(preset))
