"""Einrichtungsdialog (Config Flow) für die CF Group Wärmepumpe."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector

from .api import (
    CFGroupApiError,
    CFGroupAsyncClient,
    CFGroupAuthenticationError,
    CFGroupConnectionError,
)
from .const import (
    CONF_CLOUD_URL,
    CONF_MODEL_TYPE,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    DEFAULT_CLOUD_URL,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MIN_UPDATE_INTERVAL,
    MODEL_TEP0001,
    MODEL_TEP0004,
)

_MODEL_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(
                value=MODEL_TEP0001, label="TEP0001 – Heating only (pool heat pump)"
            ),
            selector.SelectOptionDict(
                value=MODEL_TEP0004, label="TEP0004 – Heating / Cooling / Auto"
            ),
        ],
    )
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CLOUD_URL, default=DEFAULT_CLOUD_URL): str,
        vol.Optional(CONF_MODEL_TYPE, default=MODEL_TEP0001): _MODEL_SELECTOR,
    }
)

STEP_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


def _build_reconfigure_schema(entry: ConfigEntry) -> vol.Schema:
    """Erstellt das Schema für den Reconfigure-Dialog mit vorausgefüllten Werten."""
    return vol.Schema(
        {
            vol.Required(CONF_USERNAME, default=entry.data[CONF_USERNAME]): str,
            vol.Required(CONF_PASSWORD, default=entry.data[CONF_PASSWORD]): str,
            vol.Optional(
                CONF_CLOUD_URL,
                default=entry.data.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL),
            ): str,
            vol.Optional(
                CONF_MODEL_TYPE,
                default=entry.data.get(CONF_MODEL_TYPE, MODEL_TEP0001),
            ): _MODEL_SELECTOR,
        }
    )


async def _async_validate_credentials(
    hass,
    username: str,
    password: str,
    cloud_url: str,
) -> str:
    """Prüft die Zugangsdaten und gibt den device_code des ersten Gerätes zurück."""
    session = async_get_clientsession(hass)
    client = CFGroupAsyncClient(
        session=session,
        username=username,
        password=password,
        cloud_url=cloud_url,
    )
    await client.async_login()
    return await client.async_get_first_device_code()


class CFGroupHeatPumpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Führt den Nutzer durch die Einrichtung der Integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Erster Schritt: Zugangsdaten abfragen und prüfen."""
        errors: dict[str, str] = {}

        if user_input is not None:
            cloud_url = user_input.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL)
            try:
                device_code = await _async_validate_credentials(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    cloud_url,
                )
            except CFGroupAuthenticationError:
                errors["base"] = "invalid_auth"
            except CFGroupConnectionError:
                errors["base"] = "cannot_connect"
            except CFGroupApiError:
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(device_code)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"CF Group Wärmepumpe ({device_code})",
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_CLOUD_URL: cloud_url,
                        CONF_MODEL_TYPE: user_input.get(CONF_MODEL_TYPE, MODEL_TEP0001),
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Wird von HA ausgelöst, wenn der Coordinator ConfigEntryAuthFailed wirft."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Fragt nur das neue Passwort ab, ohne die Integration zu löschen."""
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            new_password = user_input[CONF_PASSWORD]
            try:
                await _async_validate_credentials(
                    self.hass,
                    entry.data[CONF_USERNAME],
                    new_password,
                    entry.data.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL),
                )
            except CFGroupAuthenticationError:
                errors["base"] = "invalid_auth"
            except CFGroupConnectionError:
                errors["base"] = "cannot_connect"
            except CFGroupApiError:
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data={**entry.data, CONF_PASSWORD: new_password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_SCHEMA,
            description_placeholders={"username": entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Erlaubt das nachträgliche Ändern aller Zugangsdaten."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            cloud_url = user_input.get(CONF_CLOUD_URL, DEFAULT_CLOUD_URL)
            try:
                device_code = await _async_validate_credentials(
                    self.hass,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    cloud_url,
                )
            except CFGroupAuthenticationError:
                errors["base"] = "invalid_auth"
            except CFGroupConnectionError:
                errors["base"] = "cannot_connect"
            except CFGroupApiError:
                errors["base"] = "unknown"
            else:
                # Die unique_id (= device_code) muss gleich bleiben, damit
                # bestehende Entitäten und Automationen erhalten bleiben.
                await self.async_set_unique_id(device_code)
                self._abort_if_unique_id_mismatch(reason="wrong_account")
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_CLOUD_URL: cloud_url,
                        CONF_MODEL_TYPE: user_input.get(CONF_MODEL_TYPE, MODEL_TEP0001),
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_reconfigure_schema(entry),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Gibt den Options-Flow für diese Integration zurück."""
        return CFGroupHeatPumpOptionsFlow(config_entry)


class CFGroupHeatPumpOptionsFlow(OptionsFlow):
    """Ermöglicht das spätere Anpassen des Abfrage-Intervalls."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Einziger Schritt: Abfrage-Intervall konfigurieren."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self._config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            DEFAULT_UPDATE_INTERVAL,
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL,
                    default=current_interval,
                ): vol.All(int, vol.Range(min=MIN_UPDATE_INTERVAL)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
