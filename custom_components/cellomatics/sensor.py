"""Sensor entities for Cellomatics Irrigation."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_SITE_ID, DOMAIN
from .coordinator import CellomaticsCoordinator
from .entity import CellomaticsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cellomatics sensors from a config entry."""
    coordinator: CellomaticsCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    site_id = entry.data[CONF_SITE_ID]

    entities = [
        CellomaticsFlowSensor(coordinator, site_id, "flow_main", "Main Flow Rate"),
        CellomaticsFlowSensor(coordinator, site_id, "flow2", "Zone 2 Flow Rate"),
        CellomaticsFlowSensor(coordinator, site_id, "fert_flow", "Fertilizer Flow Rate"),
        CellomaticsCounterSensor(coordinator, site_id, "ctr_main", "Main Flow Counter"),
        CellomaticsCounterSensor(coordinator, site_id, "ctr2", "Zone 2 Flow Counter"),
        CellomaticsCounterSensor(coordinator, site_id, "fert_ctr", "Fertilizer Flow Counter"),
        CellomaticsBatterySensor(coordinator, site_id),
        CellomaticsStatusSensor(coordinator, site_id),
        CellomaticsWaterTodaySensor(coordinator, site_id),
    ]
    async_add_entities(entities)


class CellomaticsFlowSensor(CellomaticsEntity, SensorEntity):
    """Live flow rate sensor (L/h)."""

    _attr_device_class = SensorDeviceClass.VOLUME_FLOW_RATE
    _attr_native_unit_of_measurement = "L/h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: CellomaticsCoordinator, site_id: str, key: str, name: str
    ) -> None:
        super().__init__(coordinator, site_id)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{site_id}_{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class CellomaticsCounterSensor(CellomaticsEntity, SensorEntity):
    """Cumulative flow counter sensor (liters)."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "L"

    def __init__(
        self, coordinator: CellomaticsCoordinator, site_id: str, key: str, name: str
    ) -> None:
        super().__init__(coordinator, site_id)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{site_id}_{key}"

    @property
    def native_value(self):
        return self.coordinator.data.get(self._key)


class CellomaticsBatterySensor(CellomaticsEntity, SensorEntity):
    """Battery voltage sensor (mV)."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "mV"
    _attr_name = "Battery"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: CellomaticsCoordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_battery"

    @property
    def native_value(self):
        return self.coordinator.data.get("battery")


class CellomaticsStatusSensor(CellomaticsEntity, SensorEntity):
    """Current irrigation status (idle/running)."""

    _attr_name = "Status"

    def __init__(self, coordinator: CellomaticsCoordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("status")

    @property
    def extra_state_attributes(self):
        attrs = {}
        raw = self.coordinator.data.get("raw")
        if raw:
            attrs["raw"] = raw
        last_update = self.coordinator.data.get("last_update")
        if last_update:
            attrs["last_update"] = last_update
        return attrs or None


class CellomaticsWaterTodaySensor(CellomaticsEntity, SensorEntity):
    """Total water used today (liters), zone 1.2."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "L"
    _attr_name = "Water Used Today"

    def __init__(self, coordinator: CellomaticsCoordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_water_today"

    @property
    def native_value(self):
        return self.coordinator.data.get("water_today")
