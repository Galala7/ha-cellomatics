"""Config flow for the Cellomatics Irrigation integration."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import CellomaticsApi
from .const import CONF_SITE_ID, CONF_VALVE_COUNT, DEFAULT_VALVE_COUNT, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SITE_ID): str,
    }
)


class CellomaticsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Cellomatics Irrigation."""

    VERSION = 1

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
