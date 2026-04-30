"""Switch-Entity für das Ein-/Ausschalten der Wärmepumpe."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CFGroupConfigEntry
from .entity import CFGroupHeatPumpEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CFGroupConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet den Power-Schalter für einen Config Entry ein."""
    coordinator = entry.runtime_data
    async_add_entities([CFGroupHeatPumpPowerSwitch(coordinator)])


class CFGroupHeatPumpPowerSwitch(CFGroupHeatPumpEntity, SwitchEntity):
    """Schaltet die Wärmepumpe direkt ein oder aus."""

    _attr_translation_key = "power"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_code}_power"

    @property
    def is_on(self) -> bool | None:
        """Gibt zurück, ob die Wärmepumpe aktuell eingeschaltet ist."""
        data = self.coordinator.data
        if data is None or data.power is None:
            return None
        return data.is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Schaltet die Wärmepumpe ein."""
        await self.coordinator.client.async_set_power(self._device_code, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Schaltet die Wärmepumpe aus."""
        await self.coordinator.client.async_set_power(self._device_code, False)
        await self.coordinator.async_request_refresh()
