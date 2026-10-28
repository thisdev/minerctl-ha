"""Sensoren: Hashrate, Leistung, Effizienz, Temperaturen, Lüfter, Pool, Zustand."""
from __future__ import annotations

from typing import Any, Callable, Optional

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import REVOLUTIONS_PER_MINUTE, EntityCategory, UnitOfPower, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import MinerConfigEntry
from .entity import ConfigEntity, LiveEntity, MinerEntity

THS = "TH/s"


def _tuner(d: dict) -> dict:
    t = d.get("tunerstatus") or []
    return t[0] if t else {}


def _power(d: dict) -> Optional[float]:
    v = _tuner(d).get("ApproximateMinerPowerConsumption")
    return round(v) if isinstance(v, (int, float)) and v > 0 else None


def _dev(d: dict, cid: int) -> dict:
    return next((x for x in d.get("devs") or [] if x.get("ID") == cid), {})


def _temp(d: dict, cid: int, field: str) -> Optional[float]:
    t = next((x for x in d.get("temps") or [] if x.get("ID") == cid), {})
    v = t.get(field)
    return round(v, 1) if isinstance(v, (int, float)) and v > 0 else None


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry, add: AddEntitiesCallback) -> None:
    co = entry.runtime_data
    ents: list[SensorEntity] = [
        StateSensor(co),
        Live(co, "hashrate", "Hashrate", THS, lambda d: round(d["hash_5s"], 2) if d.get("hash_5s") else 0,
             icon="mdi:pickaxe"),
        Live(co, "hashrate_avg", "Hashrate Durchschnitt", THS,
             lambda d: round(d["hash_av"], 2) if d.get("hash_av") else None, icon="mdi:pickaxe"),
        Live(co, "power", "Leistung", UnitOfPower.WATT, _power, device_class=SensorDeviceClass.POWER),
        Live(co, "efficiency", "Effizienz", "J/TH",
             lambda d: round(_power(d) / d["hash_5s"], 1) if _power(d) and d.get("hash_5s") else None,
             icon="mdi:leaf"),
        PowerLimitSensor(co),
        Live(co, "pool", "Pool", None, lambda d: (d.get("pools") or [{}])[0].get("Status"),
             icon="mdi:server-network", entity_category=EntityCategory.DIAGNOSTIC,
             attrs=lambda d: {"url": (d.get("pools") or [{}])[0].get("URL")}),
    ]
    for cid in sorted(((co.data or {}).get("config") or {}).get("chains", {6: 1, 7: 1, 8: 1})):
        ents += [
            Live(co, f"hashrate_{cid}", f"Board {cid} Hashrate", THS,
                 lambda d, c=cid: round(_dev(d, c).get("MHS 5s", 0) / 1e6, 2) if _dev(d, c) else None,
                 icon="mdi:chip"),
            Live(co, f"chip_temp_{cid}", f"Board {cid} Chiptemperatur", UnitOfTemperature.CELSIUS,
                 lambda d, c=cid: _temp(d, c, "Chip"), device_class=SensorDeviceClass.TEMPERATURE),
            Live(co, f"board_temp_{cid}", f"Board {cid} Temperatur", UnitOfTemperature.CELSIUS,
                 lambda d, c=cid: _temp(d, c, "Board"), device_class=SensorDeviceClass.TEMPERATURE,
                 entity_category=EntityCategory.DIAGNOSTIC),
        ]
    fans = (co.data or {}).get("fans") or [{"ID": 0}, {"ID": 1}]
    for i, fan in enumerate(fans):
        fid = fan.get("ID", i)
        ents.append(Live(co, f"fan_{fid}", f"Lüfter {i + 1}", REVOLUTIONS_PER_MINUTE,
                         lambda d, f=fid: next((x.get("RPM") for x in d.get("fans") or [] if x.get("ID") == f), None),
                         icon="mdi:fan", entity_category=EntityCategory.DIAGNOSTIC))
    add(ents)


class Live(LiveEntity, SensorEntity):
    def __init__(self, co, key: str, name: str, unit: Optional[str], fn: Callable[[dict], Any], *,
                 device_class=None, icon=None, entity_category=None,
                 attrs: Optional[Callable[[dict], dict]] = None) -> None:
        super().__init__(co, key)
        self._fn, self._attrs = fn, attrs
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_icon = icon
        self._attr_entity_category = entity_category
        if unit:
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        try:
            return self._fn(self.data)
        except (KeyError, TypeError, ZeroDivisionError):
            return None

    @property
    def extra_state_attributes(self):
        return self._attrs(self.data) if self._attrs else None


class PowerLimitSensor(ConfigEntity, SensorEntity):
    _attr_name = "Leistungsgrenze aktiv"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, co) -> None:
        super().__init__(co, "power_limit_active")

    @property
    def native_value(self):
        scaled = (_tuner(self.data).get("DynamicPowerScaling") or {})
        if isinstance(scaled, dict) and scaled.get("ScaledPowerLimit"):
            return scaled["ScaledPowerLimit"]
        return self.cfg.get("power_limit")

    @property
    def extra_state_attributes(self):
        return {"konfiguriert": self.cfg.get("power_limit"), "autotuning": self.cfg.get("autotuning")}


class StateSensor(MinerEntity, SensorEntity):
    """Zustand als Text: läuft, gestoppt, Änderung läuft …, Fehler."""
    _attr_name = "Zustand"
    _attr_icon = "mdi:state-machine"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["läuft", "gestoppt", "änderung", "nicht erreichbar"]

    def __init__(self, co) -> None:
        super().__init__(co, "state")

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self):
        if self.coordinator.busy:
            return "änderung"
        if not self.coordinator.last_update_success:
            return "nicht erreichbar"
        return "läuft" if self.data.get("online") else "gestoppt"

    @property
    def extra_state_attributes(self):
        cfg = self.cfg
        return {
            "änderung": self.coordinator.busy,
            "letzter_fehler": self.coordinator.last_error,
            "preset": self.coordinator.current_preset(),
            "aktive_boards": [c for c, on in (cfg.get("chains") or {}).items() if on],
            "autotuning": cfg.get("autotuning"),
        }
