"""Climate-Entity für die CF Group Wärmepumpe."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CFGroupConfigEntry
from .const import FALLBACK_MAX_TEMP, FALLBACK_MIN_TEMP, TEMP_STEP
from .entity import CFGroupHeatPumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CFGroupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Climate-Entity für einen Config Entry ein."""
    coordinator = entry.runtime_data
    async_add_entities([CFGroupHeatPumpClimate(coordinator)])


class CFGroupHeatPumpClimate(CFGroupHeatPumpEntity, ClimateEntity):
    """Steuert die Wärmepumpe als Heizung über das Climate-Interface."""

    _attr_translation_key = "heatpump"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TEMP_STEP
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_code}_climate"

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Gibt den aktuellen Betriebsmodus zurück."""
        data = self.coordinator.data
        if data is None or data.power is None:
            return None
        return HVACMode.HEAT if data.is_on else HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Gibt zurück, ob die Wärmepumpe gerade aktiv heizt."""
        data = self.coordinator.data
        if data is None or not data.is_on:
            return HVACAction.OFF
        state = data.raw_values.get("State_mode")
        if state == "1":
            return HVACAction.HEATING
        if state == "17":
            return HVACAction.DEFROSTING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Gibt die aktuelle Einlass-Temperatur als Ist-Temperatur zurück."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.inlet_temperature

    @property
    def target_temperature(self) -> float | None:
        """Gibt die gewünschte Zieltemperatur zurück."""
        data = self.coordinator.data
        if data is None:
            return None
        return data.target_temperature

    @property
    def min_temp(self) -> float:
        """Gibt die untere Grenze für die Zieltemperatur zurück."""
        data = self.coordinator.data
        if data is not None and data.min_temperature is not None:
            return data.min_temperature
        return FALLBACK_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Gibt die obere Grenze für die Zieltemperatur zurück."""
        data = self.coordinator.data
        if data is not None and data.max_temperature is not None:
            return data.max_temperature
        return FALLBACK_MAX_TEMP

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Schaltet die Wärmepumpe ein oder aus."""
        enabled = hvac_mode == HVACMode.HEAT
        await self.coordinator.client.async_set_power(self._device_code, enabled)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Setzt die Zieltemperatur unter Berücksichtigung der Grenzwerte."""
        requested = kwargs.get(ATTR_TEMPERATURE)
        if requested is None:
            return

        clamped = max(self.min_temp, min(self.max_temp, float(requested)))
        await self.coordinator.client.async_set_target_temperature(
            self._device_code, clamped
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Komfort-Methode: Wärmepumpe einschalten."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Komfort-Methode: Wärmepumpe ausschalten."""
        await self.async_set_hvac_mode(HVACMode.OFF)
