"""Gemeinsame Basis für alle Entitäten eines Miners."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MinerCoordinator


class MinerEntity(CoordinatorEntity[MinerCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: MinerCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        cfg = (coordinator.data or {}).get("config") or {}
        ver = coordinator.version or {}
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Bitmain",
            model=cfg.get("model") or "Antminer",
            sw_version=ver.get("BOSminer") or ver.get("BOSer"),
            configuration_url=f"http://{coordinator.client.host}",
        )

    @property
    def data(self) -> dict:
        return self.coordinator.data or {}

    @property
    def cfg(self) -> dict:
        return self.data.get("config") or {}


class ConfigEntity(MinerEntity):
    """Entität, die auf der Config beruht (per SSH) – auch verfügbar, wenn das Mining gestoppt ist."""

    @property
    def available(self) -> bool:
        return super().available and bool(self.cfg)


class LiveEntity(MinerEntity):
    """Entität, die Laufzeitdaten der API braucht."""

    @property
    def available(self) -> bool:
        return super().available and bool(self.data.get("online"))
