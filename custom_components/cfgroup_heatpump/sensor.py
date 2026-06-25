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
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CFGroupConfigEntry
from .api import HeatPumpData
from .const import CONF_MODEL_TYPE, MODEL_TEP0001, MODEL_TEP0004
from .entity import CFGroupHeatPumpEntity

_STATE_MODE_LABELS: dict[str, str] = {
    "0": "cooling",
    "1": "heating",
    "17": "defrost",
}

_STATE_MODE_OPTIONS: list[str] = [*list(_STATE_MODE_LABELS.values()), "idle"]


def _state_mode_label(data: HeatPumpData) -> str | None:
    """Gibt den lesbaren Betriebszustand zurück."""
    raw = data.raw_values.get("State_mode")
    if raw is None or raw == "":
        if data.is_on:
            return "idle"
        return None
    state_str = str(raw)
    if state_str == "1":
        inlet = data.inlet_temperature
        target = data.target_temperature
        if inlet is not None and target is not None and inlet >= target:
            return "idle"
    label = _STATE_MODE_LABELS.get(state_str)
    if label is not None:
        return label
    if data.is_on:
        return "idle"
    return None


def _cloud_status_value(data: HeatPumpData) -> str | None:
    """Liest den Online-/Offline-Status aus den Daten als kleingeschriebener String."""
    status = data.device_status
    if status is None or status.status is None:
        return None
    return status.status.lower()


@dataclass(frozen=True, kw_only=True)
class CFGroupSensorEntityDescription(SensorEntityDescription):
    """Beschreibung eines Wärmepumpen-Sensors."""

    value_fn: Callable[[HeatPumpData], float | str | None]


def _temp_sensor(
    key: str,
    value_fn: Callable[[HeatPumpData], float | None],
) -> CFGroupSensorEntityDescription:
    """Erstellt eine Temperatursensor-Beschreibung mit Standard-Einstellungen."""
    return CFGroupSensorEntityDescription(
        key=key,
        translation_key=key,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        value_fn=value_fn,
    )


_TARGET_TEMPERATURE_DESCRIPTION = _temp_sensor(
    "target_temperature", lambda data: data.target_temperature
)

_TEP0004_TARGET_TEMP_DESCRIPTIONS: tuple[CFGroupSensorEntityDescription, ...] = (
    _temp_sensor("target_temperature_cooling", lambda data: data.cooling_temperature),
    _temp_sensor("target_temperature_heating", lambda data: data.heating_temperature),
    _temp_sensor("target_temperature_auto", lambda data: data.auto_temperature),
)


TEMPERATURE_DESCRIPTIONS: tuple[CFGroupSensorEntityDescription, ...] = (
    _temp_sensor("inlet_temperature", lambda data: data.inlet_temperature),
    _temp_sensor("coil_temperature", lambda data: data.coil_temperature),
    _temp_sensor("ambient_temperature", lambda data: data.ambient_temperature),
    _TARGET_TEMPERATURE_DESCRIPTION,
    _temp_sensor("outlet_temperature", lambda data: data.outlet_temperature),
    _temp_sensor("exhaust_temperature", lambda data: data.exhaust_temperature),
    CFGroupSensorEntityDescription(
        key="mode",
        translation_key="mode",
        value_fn=lambda data: data.mode,
    ),
)


DIAGNOSTIC_DESCRIPTIONS: tuple[CFGroupSensorEntityDescription, ...] = (
    CFGroupSensorEntityDescription(
        key="state_mode",
        translation_key="state_mode",
        device_class=SensorDeviceClass.ENUM,
        options=_STATE_MODE_OPTIONS,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_state_mode_label,
    ),
    CFGroupSensorEntityDescription(
        key="cloud_status",
        translation_key="cloud_status",
        device_class=SensorDeviceClass.ENUM,
        options=["online", "offline"],
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_cloud_status_value,
    ),
)


_RETURN_AIR_TEMP_DESCRIPTION = _temp_sensor(
    "return_air_temperature", lambda data: data.return_air_temperature
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CFGroupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet alle Sensoren für einen Config Entry ein."""
    coordinator = entry.runtime_data
    model_type = entry.data.get(CONF_MODEL_TYPE, MODEL_TEP0001)

    if model_type == MODEL_TEP0004:
        # TEP0004: replace the generic target_temperature with three mode-specific sensors
        temp_descriptions = tuple(
            d for d in TEMPERATURE_DESCRIPTIONS if d is not _TARGET_TEMPERATURE_DESCRIPTION
        )
        extra: tuple[CFGroupSensorEntityDescription, ...] = (
            *_TEP0004_TARGET_TEMP_DESCRIPTIONS,
            _RETURN_AIR_TEMP_DESCRIPTION,
        )
    else:
        temp_descriptions = TEMPERATURE_DESCRIPTIONS
        extra = ()

    async_add_entities(
        CFGroupHeatPumpSensor(coordinator, description)
        for description in (*temp_descriptions, *DIAGNOSTIC_DESCRIPTIONS, *extra)
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
