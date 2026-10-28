"""Einrichtung über die Oberfläche: IP, SSH-Zugang; Optionen: Abfrageintervall und Presets."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback

from .client import BosMiner, MinerError
from .const import (CONF_SCAN_INTERVAL, DEFAULT_NAME, DEFAULT_PRESETS, DEFAULT_SCAN_INTERVAL, DEFAULT_USER,
                    DOMAIN, POWER_MAX, POWER_MIN)


class MinerctlConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        placeholders = {"error": ""}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            client = BosMiner(host, user_input[CONF_USERNAME], user_input.get(CONF_PASSWORD, ""))
            try:
                cfg = await client.config_state()
            except MinerError as err:
                errors["base"] = "cannot_connect"
                placeholders["error"] = f"\n\n**Fehler:** {err}"
            else:
                await client.close()
                title = user_input.get(CONF_NAME) or cfg.get("model") or DEFAULT_NAME
                data = {CONF_HOST: host, CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, "")}
                return self.async_create_entry(title=title, data=data)
            await client.close()

        schema = vol.Schema({
            vol.Required(CONF_HOST, default=(user_input or {}).get(CONF_HOST, "")): str,
            vol.Optional(CONF_NAME, default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Required(CONF_USERNAME, default=DEFAULT_USER): str,
            vol.Optional(CONF_PASSWORD, default=""): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors,
                                    description_placeholders=placeholders)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return MinerctlOptionsFlow()


class MinerctlOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        current = {k: dict(v) for k, v in DEFAULT_PRESETS.items()}
        for k, v in (self.config_entry.options.get("presets") or {}).items():
            if k in current:
                current[k].update(v)

        if user_input is not None:
            presets = {key: {"power": int(user_input[f"{key}_power"])} for key in current}
            return self.async_create_entry(data={
                CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]), "presets": presets})

        fields: dict[Any, Any] = {
            vol.Required(CONF_SCAN_INTERVAL,
                         default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)):
                vol.All(vol.Coerce(int), vol.Range(min=5, max=600)),
        }
        for key, p in current.items():
            fields[vol.Required(f"{key}_power", default=p["power"])] = vol.All(
                vol.Coerce(int), vol.Range(min=POWER_MIN, max=POWER_MAX))
        return self.async_show_form(step_id="init", data_schema=vol.Schema(fields))
