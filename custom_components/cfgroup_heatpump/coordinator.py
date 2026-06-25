"""DataUpdateCoordinator für die CF Group Wärmepumpe."""

from __future__ import annotations

from dataclasses import replace
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
    DeviceStatus,
    FaultEntry,
    HeatPumpData,
)
from .const import DOMAIN, MAX_FAILED_UPDATES_BEFORE_UNAVAILABLE

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
        # Anzahl aufeinanderfolgender fehlgeschlagener Polls. Wird bei jedem
        # Erfolg auf 0 zurückgesetzt. Solange der Wert unter dem Limit liegt,
        # behalten die Entitäten den letzten erfolgreichen Wert.
        self._consecutive_failures: int = 0

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
        await self._async_ensure_device_code()

    async def _async_ensure_device_code(self) -> None:
        """Holt den device_code, falls er noch nicht bekannt ist."""
        if self._device_code is not None:
            return
        try:
            self._device_code = await self._client.async_get_first_device_code()
        except CFGroupAuthenticationError as error:
            raise ConfigEntryAuthFailed(str(error)) from error
        except CFGroupApiError as error:
            raise UpdateFailed(str(error)) from error

    async def _async_update_data(self) -> HeatPumpData:
        """Wird regelmäßig durch den Coordinator aufgerufen.

        Strategie:
        * Vorab den schlanken `getDeviceStatus`-Endpoint anfragen.
          Bei OFFLINE wird `getDataByCode` übersprungen und der letzte
          Cache mit aktualisiertem Status zurückgegeben. Beim allerersten
          Update ohne Cache liefert die Methode einen leeren `HeatPumpData`,
          damit Diagnose-Sensoren (Cloud-Status, Störung) korrekt sind.
        * Bei ONLINE läuft der bestehende Pfad: `getDataByCode` für die
          eigentlichen Messwerte, plus Diagnose-Daten.
        * Auth-Fehler nach erfolglosem Re-Login → ConfigEntryAuthFailed
          (löst den Reauth-Flow von Home Assistant aus).
        * Verbindungs-/Antwort-Fehler werden bis zu
          MAX_FAILED_UPDATES_BEFORE_UNAVAILABLE-mal toleriert: Solange
          bleibt der letzte erfolgreiche Wert erhalten. Erst danach
          UpdateFailed und Entitäten gehen auf "nicht verfügbar".
        """
        # Falls _async_setup beim Initialisieren fehlschlug, hier nachholen.
        await self._async_ensure_device_code()

        device_status = await self._async_fetch_status_safely()

        if device_status is not None and not device_status.is_online:
            _LOGGER.debug(
                "Cloud meldet Gerät als '%s'; getDataByCode wird übersprungen.",
                device_status.status,
            )
            faults = await self._async_fetch_faults_safely()
            self._consecutive_failures = 0
            cached = self.data
            if cached is not None:
                return replace(
                    cached, device_status=device_status, faults=tuple(faults)
                )
            return HeatPumpData.empty(device_status=device_status, faults=tuple(faults))

        try:
            data = await self._client.async_get_heatpump_data(self.device_code)
        except CFGroupAuthenticationError as error:
            # Der API-Client hat bereits einmal automatisch neu eingeloggt.
            # Wenn der Auth-Fehler trotzdem hier ankommt, sind die Zugangs-
            # daten dauerhaft ungültig und der Nutzer muss eingreifen.
            raise ConfigEntryAuthFailed(str(error)) from error
        except (CFGroupConnectionError, CFGroupApiError) as error:
            return self._handle_update_failure(error)

        # Status nachholen, falls der Vorab-Versuch fehlschlug.
        if device_status is None:
            device_status = await self._async_fetch_status_safely()
        faults = await self._async_fetch_faults_safely()

        self._consecutive_failures = 0
        return replace(data, device_status=device_status, faults=tuple(faults))

    async def _async_fetch_status_safely(self) -> DeviceStatus | None:
        """Holt den Geräte-Status; loggt Fehler, ohne den Update abzubrechen."""
        try:
            return await self._client.async_get_device_status(self.device_code)
        except CFGroupAuthenticationError:
            # Auth-Fehler werden im Hauptpfad behandelt; hier nur ignorieren.
            raise
        except CFGroupApiError as error:
            _LOGGER.debug("Geräte-Status konnte nicht geholt werden: %s", error)
            return None

    async def _async_fetch_faults_safely(self) -> list[FaultEntry]:
        """Holt die aktive Fehlerliste; loggt Fehler, ohne abzubrechen."""
        try:
            return await self._client.async_get_fault_data(self.device_code)
        except CFGroupAuthenticationError:
            raise
        except CFGroupApiError as error:
            _LOGGER.debug("Fehlerliste konnte nicht geholt werden: %s", error)
            return []

    def _handle_update_failure(self, error: Exception) -> HeatPumpData:
        """Behandelt einen fehlgeschlagenen Poll mit Cache-Toleranz."""
        self._consecutive_failures += 1
        last_data = self.data
        if (
            last_data is not None
            and self._consecutive_failures <= MAX_FAILED_UPDATES_BEFORE_UNAVAILABLE
        ):
            _LOGGER.warning(
                "Cloud-Abruf fehlgeschlagen (%d/%d), behalte letzte Werte: %s",
                self._consecutive_failures,
                MAX_FAILED_UPDATES_BEFORE_UNAVAILABLE,
                error,
            )
            return last_data
        raise UpdateFailed(str(error)) from error
