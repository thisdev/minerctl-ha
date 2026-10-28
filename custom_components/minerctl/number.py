"""Leistungsgrenze als Zahlenfeld."""
from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .const import POWER_MAX, POWER_MIN, POWER_STEP
from .entity import ConfigEntity


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    add([PowerLimit(entry.runtime_data)])


class PowerLimit(ConfigEntity, NumberEntity):
    _attr_name = "Leistungsgrenze"
    _attr_icon = "mdi:flash"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = POWER_MIN
    _attr_native_max_value = POWER_MAX
    _attr_native_step = POWER_STEP
    _attr_mode = NumberMode.BOX

    def __init__(self, co) -> None:
        super().__init__(co, "power_limit")

    @property
    def native_value(self):
        return self.cfg.get("power_limit")

    async def async_set_native_value(self, value: float) -> None:
        watts = int(round(value))
        if watts == self.cfg.get("power_limit") and self.cfg.get("autotuning"):
            return
        await self.coordinator.run_change(f"Leistung {watts} W", lambda: self.coordinator.client.set_power(watts))
