"""Integration für die CF Group Wärmepumpe."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CFGroupAsyncClient
from .const import (
    CONF_CLOUD_URL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_CLOUD_URL,
    DEFAULT_UPDATE_INTERVAL,
)
from .coordinator import CFGroupHeatPumpCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.SWITCH,
]

type CFGroupConfigEntry = ConfigEntry[CFGroupHeatPumpCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: CFGroupConfigEntry) -> bool:
    """Richtet die Integration anhand eines Config-Entry ein."""
    session = async_get_clientsession(hass)

    client = CFGroupAsyncClient(
        session=session,
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        cloud_url=entry.data.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL),
    )

    update_interval = entry.options.get(
        CONF_UPDATE_INTERVAL,
        entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )

    coordinator = CFGroupHeatPumpCoordinator(
        hass=hass,
        entry=entry,
        client=client,
        update_interval_seconds=int(update_interval),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CFGroupConfigEntry) -> bool:
    """Entfernt die Integration sauber."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_update_options(hass: HomeAssistant, entry: CFGroupConfigEntry) -> None:
    """Lädt die Integration neu, wenn die Optionen geändert wurden."""
    await hass.config_entries.async_reload(entry.entry_id)
