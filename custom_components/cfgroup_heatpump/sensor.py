"""Sensor-Entities für die CF Group Wärmepumpe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CFGroupConfigEntry
from .api import HeatPumpData
from .entity import CFGroupHeatPumpEntity


@dataclass(frozen=True, kw_only=True)
class CFGroupSensorEntityDescription(SensorEntityDescription):
    """Beschreibung eines Wärmepumpen-Sensors."""

    value_fn: Callable[[HeatPumpData], float | str | None]


TEMPERATURE_DESCRIPTIONS: tuple[CFGroupSensorEntityDescription, ...] = (
    CFGroupSensorEntityDescription(
        key="inlet_temperature",
        translation_key="inlet_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.inlet_temperature,
    ),
    CFGroupSensorEntityDescription(
        key="coil_temperature",
        translation_key="coil_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.coil_temperature,
    ),
    CFGroupSensorEntityDescription(
        key="ambient_temperature",
        translation_key="ambient_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.ambient_temperature,
    ),
    CFGroupSensorEntityDescription(
        key="target_temperature",
        translation_key="target_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=lambda data: data.target_temperature,
    ),
    CFGroupSensorEntityDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda data: data.mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CFGroupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet alle Sensoren für einen Config Entry ein."""
    coordinator = entry.runtime_data
    async_add_entities(
        CFGroupHeatPumpSensor(coordinator, description)
        for description in TEMPERATURE_DESCRIPTIONS
    )


class CFGroupHeatPumpSensor(CFGroupHeatPumpEntity, SensorEntity):
    """Repräsentiert einen einzelnen Messwert."""

    entity_description: CFGroupSensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: CFGroupSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._device_code}_{description.key}"

    @property
    def native_value(self) -> float | str | None:
        """Gibt den aktuellen Sensorwert zurück."""
        return self.entity_description.value_fn(self.coordinator.data)
