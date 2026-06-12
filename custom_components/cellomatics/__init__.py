"""The Cellomatics Irrigation integration."""

from __future__ import annotations

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import CellomaticsApi, CellomaticsAuthError
from .const import CONF_SITE_ID, DOMAIN
from .coordinator import CellomaticsCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

# /api/call can take several seconds for the cellular controller to respond
# (and may occasionally hang); bound every request well below aiohttp's
# 5 minute default so a stuck request can't block the coordinator.
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=60)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Cellomatics Irrigation from a config entry."""
    jar = aiohttp.CookieJar(unsafe=True)
    session = aiohttp.ClientSession(cookie_jar=jar, timeout=_REQUEST_TIMEOUT)

    api = CellomaticsApi(
        session,
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data[CONF_SITE_ID],
    )

    coordinator = CellomaticsCoordinator(hass, api)

    try:
        await coordinator.async_setup()
    except CellomaticsAuthError as err:
        await session.close()
        raise ConfigEntryNotReady(
            f"Unable to authenticate with Cellomatics: {err}"
        ) from err
    except Exception:
        await session.close()
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "session": session,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        data["coordinator"].unload()
        await data["session"].close()

    return unload_ok
