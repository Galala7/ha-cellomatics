"""Binary sensor entities (valves) for Cellomatics Irrigation."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SITE_ID, CONF_VALVE_COUNT, DEFAULT_VALVE_COUNT, DOMAIN
from .coordinator import CellomaticsCoordinator
from .entity import CellomaticsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cellomatics valve binary sensors from a config entry."""
    coordinator: CellomaticsCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    site_id = entry.data[CONF_SITE_ID]
    valve_count = entry.data.get(CONF_VALVE_COUNT, DEFAULT_VALVE_COUNT)

    entities = [
        CellomaticsValveSensor(coordinator, site_id, index)
        for index in range(valve_count)
    ]
    entities.append(CellomaticsSuspendedSensor(coordinator, site_id))
    async_add_entities(entities)


class CellomaticsValveSensor(CellomaticsEntity, BinarySensorEntity):
    """Represents a single irrigation valve's open/closed state."""

    _attr_device_class = BinarySensorDeviceClass.OPENING

    def __init__(
        self, coordinator: CellomaticsCoordinator, site_id: str, index: int
    ) -> None:
        super().__init__(coordinator, site_id)
        self._index = index
        self._attr_name = f"Valve {index + 1}"
        self._attr_unique_id = f"{site_id}_valve_{index + 1}"

    @property
    def is_on(self) -> bool | None:
        valves = self.coordinator.data.get("valves")
        if valves and self._index < len(valves):
            return valves[self._index]
        return None


class CellomaticsSuspendedSensor(CellomaticsEntity, BinarySensorEntity):
    """Whether the controller is currently suspended/disabled (ENA != 1).

    This reflects the controller's overall enabled flag (`ENA:`), which is
    e.g. set to a non-1 value while irrigation is paused via the portal's
    "suspend for N days" feature. The API does not expose the remaining
    suspend duration - only whether it's currently suspended.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_name = "Suspended"

    def __init__(self, coordinator: CellomaticsCoordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_suspended"

    @property
    def is_on(self) -> bool | None:
        enabled = self.coordinator.data.get("enabled")
        if enabled is None:
            return None
        return not enabled
