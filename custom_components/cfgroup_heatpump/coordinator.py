"""DataUpdateCoordinator für die CF Group Wärmepumpe."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CFGroupApiError,
    CFGroupAsyncClient,
    CFGroupAuthenticationError,
    CFGroupConnectionError,
    HeatPumpData,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class CFGroupHeatPumpCoordinator(DataUpdateCoordinator[HeatPumpData]):
    """Zentraler Taktgeber für den Datenabruf der Wärmepumpe."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: CFGroupAsyncClient,
        update_interval_seconds: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            config_entry=entry,
            update_interval=timedelta(seconds=update_interval_seconds),
        )
        self._client = client
        self._device_code: str | None = None

    @property
    def client(self) -> CFGroupAsyncClient:
        """Gibt den API-Client zurück."""
        return self._client

    @property
    def device_code(self) -> str:
        """Gibt den device_code zurück oder wirft einen Fehler."""
        if self._device_code is None:
            raise RuntimeError("Der Coordinator wurde noch nicht initialisiert.")
        return self._device_code

    async def _async_setup(self) -> None:
        """Wird einmalig vor dem ersten Datenabruf ausgeführt."""
        try:
            self._device_code = await self._client.async_get_first_device_code()
        except CFGroupAuthenticationError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except CFGroupApiError as error:
            raise UpdateFailed(str(error)) from error

    async def _async_update_data(self) -> HeatPumpData:
        """Wird regelmäßig durch den Coordinator aufgerufen."""
        try:
            return await self._client.async_get_heatpump_data(self.device_code)
        except CFGroupAuthenticationError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except CFGroupConnectionError as error:
            raise UpdateFailed(str(error)) from error
        except CFGroupApiError as error:
            raise UpdateFailed(str(error)) from error
