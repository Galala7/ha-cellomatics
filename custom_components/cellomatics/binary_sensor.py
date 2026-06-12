"""Binary sensor entities (valves) for Cellomatics Irrigation."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SITE_ID, DOMAIN
from .coordinator import CellomaticsCoordinator
from .entity import CellomaticsEntity

VALVE_COUNT = 6


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cellomatics valve binary sensors from a config entry."""
    coordinator: CellomaticsCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    site_id = entry.data[CONF_SITE_ID]

    entities = [
        CellomaticsValveSensor(coordinator, site_id, index)
        for index in range(VALVE_COUNT)
    ]
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
