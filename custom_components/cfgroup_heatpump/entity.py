"""Gemeinsame Basis-Entity für die CF Group Heat Pump Integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MANUFACTURER_URL, MODEL
from .coordinator import CFGroupHeatPumpCoordinator


class CFGroupHeatPumpEntity(CoordinatorEntity[CFGroupHeatPumpCoordinator]):
    """Basisklasse, die alle Entities derselben Wärmepumpe zusammenführt."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: CFGroupHeatPumpCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_code)},
            name="CF Group",
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=MANUFACTURER_URL,
        )

    @property
    def _device_code(self) -> str:
        return self.coordinator.device_code
