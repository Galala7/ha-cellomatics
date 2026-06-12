"""The Cellomatics Irrigation integration."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import service

from .api import CellomaticsApi, CellomaticsAuthError
from .const import CONF_SITE_ID, DOMAIN
from .coordinator import CellomaticsCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

SERVICE_FORCE_PASSIVE_UPDATE = "force_passive_update"
SERVICE_FORCE_ACTIVE_UPDATE = "force_active_update"

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

    await _async_register_services(hass)

    return True


async def _async_coordinators_for_call(
    hass: HomeAssistant, call: ServiceCall
) -> list[CellomaticsCoordinator]:
    """Resolve a service call's target device(s)/entry(ies) to coordinators.

    If no target is given, applies to every configured Cellomatics entry.
    """
    # HA Core deprecated passing `hass` to async_extract_config_entry_ids
    # (removal in 2026.10); fall back to the old signature on older cores
    # that don't accept the new hass-less form yet.
    try:
        entry_ids = await service.async_extract_config_entry_ids(call)
    except TypeError:
        entry_ids = await service.async_extract_config_entry_ids(hass, call)

    if not entry_ids:
        entry_ids = set(hass.data.get(DOMAIN, {}))

    coordinators = []
    for entry_id in entry_ids:
        entry_data = hass.data.get(DOMAIN, {}).get(entry_id)
        if entry_data:
            coordinators.append(entry_data["coordinator"])
    return coordinators


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register the force-update services once, for all config entries."""
    if hass.services.has_service(DOMAIN, SERVICE_FORCE_PASSIVE_UPDATE):
        return

    async def _handle_force_passive_update(call: ServiceCall) -> None:
        coordinators = await _async_coordinators_for_call(hass, call)
        _LOGGER.debug(
            "Cellomatics: %s service called for %d device(s)",
            SERVICE_FORCE_PASSIVE_UPDATE,
            len(coordinators),
        )
        for coordinator in coordinators:
            await coordinator.async_force_passive_update()

    async def _handle_force_active_update(call: ServiceCall) -> None:
        coordinators = await _async_coordinators_for_call(hass, call)
        _LOGGER.debug(
            "Cellomatics: %s service called for %d device(s)",
            SERVICE_FORCE_ACTIVE_UPDATE,
            len(coordinators),
        )
        for coordinator in coordinators:
            await coordinator.async_force_active_update()

    hass.services.async_register(
        DOMAIN, SERVICE_FORCE_PASSIVE_UPDATE, _handle_force_passive_update
    )
    hass.services.async_register(
        DOMAIN, SERVICE_FORCE_ACTIVE_UPDATE, _handle_force_active_update
    )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        data["coordinator"].unload()
        await data["session"].close()

        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_PASSIVE_UPDATE)
            hass.services.async_remove(DOMAIN, SERVICE_FORCE_ACTIVE_UPDATE)

    return unload_ok
