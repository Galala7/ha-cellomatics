"""Shared base entity for Cellomatics Irrigation."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CellomaticsCoordinator


class CellomaticsEntity(CoordinatorEntity[CellomaticsCoordinator]):
    """Base entity providing shared device info for all Cellomatics entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CellomaticsCoordinator, site_id: str) -> None:
        super().__init__(coordinator)
        self._site_id = site_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._site_id)},
            name=f"Cellomatics Irrigation ({self._site_id})",
            manufacturer="Cellomatics",
            model="Irrigation Controller",
        )
