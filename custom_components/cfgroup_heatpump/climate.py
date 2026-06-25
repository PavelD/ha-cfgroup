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
from .const import (
    CONF_MODEL_TYPE,
    FALLBACK_MAX_TEMP,
    FALLBACK_MAX_TEMP_TEP0004,
    FALLBACK_MIN_TEMP,
    FALLBACK_MIN_TEMP_TEP0004,
    MODE_AUTO,
    MODE_COOLING,
    MODE_HEATING,
    MODEL_TEP0001,
    MODEL_TEP0004,
    TEMP_STEP,
)
from .entity import CFGroupHeatPumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CFGroupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die Climate-Entity für einen Config Entry ein."""
    coordinator = entry.runtime_data
    model_type = entry.data.get(CONF_MODEL_TYPE, MODEL_TEP0001)
    async_add_entities([CFGroupHeatPumpClimate(coordinator, model_type)])


class CFGroupHeatPumpClimate(CFGroupHeatPumpEntity, ClimateEntity):
    """Steuert die Wärmepumpe über das Climate-Interface.

    TEP0001: Nur Heizen (HVACMode.HEAT / HVACMode.OFF).
    TEP0004: Kühlen (COOL), Heizen (HEAT), Automatik (HEAT_COOL) und Aus (OFF).
    """

    _attr_translation_key = 'heatpump'
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TEMP_STEP
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, model_type: str = MODEL_TEP0001) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f'{self._device_code}_climate'
        self._model_type = model_type

        if model_type == MODEL_TEP0004:
            self._attr_hvac_modes = [
                HVACMode.OFF,
                HVACMode.COOL,
                HVACMode.HEAT,
                HVACMode.HEAT_COOL,
            ]
        else:
            self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Gibt den aktuellen Betriebsmodus zurück."""
        data = self.coordinator.data
        if data is None or data.power is None:
            return None
        if not data.is_on:
            return HVACMode.OFF

        if self._model_type == MODEL_TEP0004:
            mode = data.mode
            if mode == MODE_COOLING:
                return HVACMode.COOL
            if mode == MODE_HEATING:
                return HVACMode.HEAT
            if mode == MODE_AUTO:
                return HVACMode.HEAT_COOL
            # Unbekannter Modus – sicher als HEAT behandeln
            return HVACMode.HEAT

        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction | None:
        """Gibt zurück, ob die Wärmepumpe gerade aktiv heizt, kühlt usw."""
        data = self.coordinator.data
        if data is None or not data.is_on:
            return HVACAction.OFF

        state = data.raw_values.get('State_mode')

        # Abtauung hat immer Vorrang
        if state == '17':
            return HVACAction.DEFROSTING

        if self._model_type == MODEL_TEP0004:
            if state == MODE_COOLING:
                return HVACAction.COOLING
            if state == MODE_HEATING:
                return HVACAction.HEATING
            return HVACAction.IDLE

        # TEP0001-Logik: State_mode "1" = Heizen (mit Idle-Erkennung)
        if state == '1':
            inlet = data.inlet_temperature
            target = data.target_temperature
            if inlet is not None and target is not None and inlet >= target:
                return HVACAction.IDLE
            return HVACAction.HEATING

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
        """Gibt den aktiven Sollwert abhängig vom Betriebsmodus zurück."""
        data = self.coordinator.data
        if data is None:
            return None

        if self._model_type == MODEL_TEP0004:
            mode = data.mode
            if mode == MODE_COOLING:
                return data.cooling_temperature
            if mode == MODE_HEATING:
                return data.heating_temperature
            if mode == MODE_AUTO:
                return data.auto_temperature
            return data.cooling_temperature  # Fallback

        return data.target_temperature

    @property
    def min_temp(self) -> float:
        """Gibt die untere Grenze für die Zieltemperatur zurück."""
        if self._model_type == MODEL_TEP0004:
            return FALLBACK_MIN_TEMP_TEP0004

        data = self.coordinator.data
        if data is not None and data.min_temperature is not None:
            return data.min_temperature
        return FALLBACK_MIN_TEMP

    @property
    def max_temp(self) -> float:
        """Gibt die obere Grenze für die Zieltemperatur zurück."""
        if self._model_type == MODEL_TEP0004:
            return FALLBACK_MAX_TEMP_TEP0004

        data = self.coordinator.data
        if data is not None and data.max_temperature is not None:
            return data.max_temperature
        return FALLBACK_MAX_TEMP

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Schaltet die Wärmepumpe ein/aus oder wechselt den Betriebsmodus."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.client.async_set_power(self._device_code, False)
        else:
            # Einschalten, falls die Pumpe aus ist
            data = self.coordinator.data
            if data is not None and not data.is_on:
                await self.coordinator.client.async_set_power(self._device_code, True)

            if self._model_type == MODEL_TEP0004:
                if hvac_mode == HVACMode.COOL:
                    await self.coordinator.client.async_set_mode(
                        self._device_code, MODE_COOLING
                    )
                elif hvac_mode == HVACMode.HEAT:
                    await self.coordinator.client.async_set_mode(
                        self._device_code, MODE_HEATING
                    )
                elif hvac_mode == HVACMode.HEAT_COOL:
                    await self.coordinator.client.async_set_mode(
                        self._device_code, MODE_AUTO
                    )

        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Setzt die Zieltemperatur unter Berücksichtigung der Grenzwerte."""
        requested = kwargs.get(ATTR_TEMPERATURE)
        if requested is None:
            return

        clamped = max(self.min_temp, min(self.max_temp, float(requested)))

        if self._model_type == MODEL_TEP0004:
            data = self.coordinator.data
            mode = data.mode if data is not None else None

            if mode == MODE_COOLING:
                await self.coordinator.client.async_set_target_temperature(
                    self._device_code, clamped
                )
            elif mode == MODE_HEATING:
                await self.coordinator.client.async_set_heating_temperature(
                    self._device_code, clamped
                )
            elif mode == MODE_AUTO:
                await self.coordinator.client.async_set_auto_temperature(
                    self._device_code, clamped
                )
            else:
                # Fallback: Kühl-Sollwert (R01)
                await self.coordinator.client.async_set_target_temperature(
                    self._device_code, clamped
                )
        else:
            await self.coordinator.client.async_set_target_temperature(
                self._device_code, clamped
            )

        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        """Komfort-Methode: Wärmepumpe einschalten."""
        await self.async_set_hvac_mode(
            HVACMode.COOL if self._model_type == MODEL_TEP0004 else HVACMode.HEAT
        )

    async def async_turn_off(self) -> None:
        """Komfort-Methode: Wärmepumpe ausschalten."""
        await self.async_set_hvac_mode(HVACMode.OFF)
