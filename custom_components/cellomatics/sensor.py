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

from .const import (
    CONF_PULSE_FACTOR_FERT,
    CONF_PULSE_FACTOR_MAIN,
    CONF_PULSE_FACTOR_ZONE2,
    CONF_SITE_ID,
    DEFAULT_PULSE_FACTOR_FERT,
    DEFAULT_PULSE_FACTOR_MAIN,
    DEFAULT_PULSE_FACTOR_ZONE2,
    DOMAIN,
)
from .coordinator import CellomaticsCoordinator
from .entity import CellomaticsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Cellomatics sensors from a config entry."""
    coordinator: CellomaticsCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    site_id = entry.data[CONF_SITE_ID]

    # Options take precedence over initial config data (options flow saves here).
    cfg = {**entry.data, **entry.options}
    pf_main = cfg.get(CONF_PULSE_FACTOR_MAIN, DEFAULT_PULSE_FACTOR_MAIN)
    pf_zone2 = cfg.get(CONF_PULSE_FACTOR_ZONE2, DEFAULT_PULSE_FACTOR_ZONE2)
    pf_fert = cfg.get(CONF_PULSE_FACTOR_FERT, DEFAULT_PULSE_FACTOR_FERT)

    entities = [
        CellomaticsFlowSensor(coordinator, site_id, "flow_main", "Main Flow Rate"),
        CellomaticsFlowSensor(coordinator, site_id, "flow2", "Zone 2 Flow Rate"),
        CellomaticsFlowSensor(coordinator, site_id, "fert_flow", "Fertilizer Flow Rate"),
        CellomaticsCounterSensor(coordinator, site_id, "ctr_main", "Main Flow Counter", pf_main),
        CellomaticsCounterSensor(coordinator, site_id, "ctr2", "Zone 2 Flow Counter", pf_zone2),
        CellomaticsCounterSensor(coordinator, site_id, "fert_ctr", "Fertilizer Flow Counter", pf_fert),
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

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "L"

    def __init__(
        self,
        coordinator: CellomaticsCoordinator,
        site_id: str,
        key: str,
        name: str,
        pulse_factor: int,
    ) -> None:
        super().__init__(coordinator, site_id)
        self._key = key
        self._pulse_factor = pulse_factor
        self._attr_name = name
        self._attr_unique_id = f"{site_id}_{key}"

    @property
    def native_value(self):
        raw = self.coordinator.data.get(self._key)
        return raw * self._pulse_factor if raw is not None else None


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
    """Current irrigation status: idle, running, or suspended.

    "suspended" reflects the controller's ENA flag being non-1, e.g. while
    the portal's "suspend irrigation for N days" feature is active. It takes
    priority over idle/running, since a suspended controller won't actually
    run any irrigation regardless of the task-status line.
    """

    _attr_name = "Status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["idle", "running", "suspended"]

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
        enabled = self.coordinator.data.get("enabled")
        if enabled is not None:
            attrs["enabled"] = enabled
        last_update = self.coordinator.data.get("last_update")
        if last_update:
            attrs["last_update"] = last_update
        return attrs or None


class CellomaticsWaterTodaySensor(CellomaticsEntity, SensorEntity):
    """Total water used today (liters), zone 1.2."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "L"
    _attr_name = "Water Used Today"

    def __init__(self, coordinator: CellomaticsCoordinator, site_id: str) -> None:
        super().__init__(coordinator, site_id)
        self._attr_unique_id = f"{site_id}_water_today"

    @property
    def native_value(self):
        return self.coordinator.data.get("water_today")
