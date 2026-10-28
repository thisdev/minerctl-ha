"""minerctl – Antminer S9 (Braiins OS) in Home Assistant steuern."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant

from .client import BosMiner
from .const import DEFAULT_USER
from .coordinator import MinerCoordinator

PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.SELECT, Platform.BUTTON]

type MinerConfigEntry = ConfigEntry[MinerCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: MinerConfigEntry) -> bool:
    client = BosMiner(entry.data[CONF_HOST], entry.data.get(CONF_USERNAME, DEFAULT_USER),
                      entry.data.get(CONF_PASSWORD, ""))
    coordinator = MinerCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    coordinator.version = await client.version()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_reload_on_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MinerConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.client.close()
    return ok


async def _reload_on_options(hass: HomeAssistant, entry: MinerConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
