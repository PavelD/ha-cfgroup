"""Binary-Sensor-Entities für Diagnose der CF Group Wärmepumpe."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CFGroupConfigEntry
from .entity import CFGroupHeatPumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CFGroupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet alle Binary-Sensoren für einen Config Entry ein."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            CFGroupHeatPumpFaultSensor(coordinator),
            CFGroupHeatPumpDefrostSensor(coordinator),
        ]
    )


class CFGroupHeatPumpFaultSensor(CFGroupHeatPumpEntity, BinarySensorEntity):
    """Zeigt aktive Fehler/Störungen der Wärmepumpe an.

    Quellen sind das `is_fault`-Flag aus `device/getDeviceStatus` und die
    Liste aktiver Fehler aus `device/getFaultDataByDeviceCode`. Die
    eigentlichen Fehler-Codes werden als Attribut `active_faults` mit
    ausgeliefert, damit sie in Automatisierungen oder Notifications
    direkt nutzbar sind.
    """

    _attr_translation_key = "fault"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_code}_fault"

    @property
    def is_on(self) -> bool | None:
        """True bei aktiver Störung, None wenn noch keine Daten vorliegen."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.has_fault

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Liefert die Liste aktiver Fehler als zusätzliches Attribut."""
        data = self.coordinator.data
        if data is None or not data.faults:
            return {}
        return {
            "active_faults": [
                {
                    "code": fault.code,
                    "description": fault.description,
                    "raw": fault.raw,
                }
                for fault in data.faults
            ]
        }


class CFGroupHeatPumpDefrostSensor(CFGroupHeatPumpEntity, BinarySensorEntity):
    """Zeigt an, ob die Wärmepumpe gerade abtaut."""

    _attr_translation_key = "defrost"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_code}_defrost"

    @property
    def is_on(self) -> bool | None:
        """True bei aktiver Abtauung, None wenn noch keine Daten vorliegen."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.is_defrosting
