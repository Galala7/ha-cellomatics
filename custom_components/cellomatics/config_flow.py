"""Config flow for the Cellomatics Irrigation integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import CellomaticsApi
from .const import (
    CONF_PULSE_FACTOR_FERT,
    CONF_PULSE_FACTOR_MAIN,
    CONF_PULSE_FACTOR_ZONE2,
    CONF_SITE_ID,
    CONF_VALVE_COUNT,
    DEFAULT_PULSE_FACTOR_FERT,
    DEFAULT_PULSE_FACTOR_MAIN,
    DEFAULT_PULSE_FACTOR_ZONE2,
    DEFAULT_VALVE_COUNT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

_PULSE_FACTOR_VALIDATOR = vol.All(vol.Coerce(int), vol.Range(min=1))

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SITE_ID): str,
        vol.Required(CONF_PULSE_FACTOR_MAIN, default=DEFAULT_PULSE_FACTOR_MAIN): _PULSE_FACTOR_VALIDATOR,
        vol.Required(CONF_PULSE_FACTOR_ZONE2, default=DEFAULT_PULSE_FACTOR_ZONE2): _PULSE_FACTOR_VALIDATOR,
        vol.Required(CONF_PULSE_FACTOR_FERT, default=DEFAULT_PULSE_FACTOR_FERT): _PULSE_FACTOR_VALIDATOR,
    }
)


def _options_schema(current: dict) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_PULSE_FACTOR_MAIN,
                default=current.get(CONF_PULSE_FACTOR_MAIN, DEFAULT_PULSE_FACTOR_MAIN),
            ): _PULSE_FACTOR_VALIDATOR,
            vol.Required(
                CONF_PULSE_FACTOR_ZONE2,
                default=current.get(CONF_PULSE_FACTOR_ZONE2, DEFAULT_PULSE_FACTOR_ZONE2),
            ): _PULSE_FACTOR_VALIDATOR,
            vol.Required(
                CONF_PULSE_FACTOR_FERT,
                default=current.get(CONF_PULSE_FACTOR_FERT, DEFAULT_PULSE_FACTOR_FERT),
            ): _PULSE_FACTOR_VALIDATOR,
        }
    )


class CellomaticsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cellomatics Irrigation."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return CellomaticsOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                jar = aiohttp.CookieJar(unsafe=True)
                async with aiohttp.ClientSession(
                    cookie_jar=jar, timeout=aiohttp.ClientTimeout(total=30)
                ) as session:
                    api = CellomaticsApi(
                        session,
                        user_input[CONF_USERNAME],
                        user_input[CONF_PASSWORD],
                        user_input[CONF_SITE_ID],
                    )
                    valid = await api.async_test_credentials()
                    valve_count = None
                    if valid:
                        valve_count = await api.async_get_valve_count()
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Cellomatics: unexpected error validating credentials")
                errors["base"] = "unknown"
            else:
                if valid:
                    await self.async_set_unique_id(user_input[CONF_SITE_ID])
                    self._abort_if_unique_id_configured()
                    data = dict(user_input)
                    data[CONF_VALVE_COUNT] = valve_count or DEFAULT_VALVE_COUNT
                    if valve_count is None:
                        _LOGGER.warning(
                            "Cellomatics: could not detect valve count, "
                            "defaulting to %s",
                            DEFAULT_VALVE_COUNT,
                        )
                    return self.async_create_entry(
                        title=f"Cellomatics ({user_input[CONF_SITE_ID]})",
                        data=data,
                    )
                errors["base"] = "auth_failed"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )


class CellomaticsOptionsFlow(config_entries.OptionsFlow):
    """Handle Cellomatics options (pulse factors per counter)."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        # Current values: options override data, fall back to defaults
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current),
        )
