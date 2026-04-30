"""Asynchroner Client für die CF Group / Linked-Go Cloud-API."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import (
    DEFAULT_APP_ID,
    DEFAULT_CLOUD_URL,
    POLLED_PROTOCOL_CODES,
    PROTOCOL_CODE_POWER,
    PROTOCOL_CODE_TARGET_TEMP,
    TOKEN_RENEWAL_SECONDS,
)


DEFAULT_TIMEOUT_SECONDS = 15


class CFGroupApiError(Exception):
    """Basisklasse für alle API-Fehler."""


class CFGroupAuthenticationError(CFGroupApiError):
    """Login-Daten wurden von der Cloud abgelehnt."""


class CFGroupConnectionError(CFGroupApiError):
    """Die Cloud ist aktuell nicht erreichbar."""


class CFGroupResponseError(CFGroupApiError):
    """Die Cloud hat eine unerwartete Antwort geliefert."""


@dataclass(frozen=True)
class HeatPumpData:
    """Aufbereitete Messwerte einer Wärmepumpe."""

    power: str | None
    mode: str | None
    mode_state: str | None
    inlet_temperature: float | None
    coil_temperature: float | None
    ambient_temperature: float | None
    target_temperature: float | None
    min_temperature: float | None
    max_temperature: float | None
    raw_values: dict[str, Any]

    @property
    def is_on(self) -> bool:
        """Gibt zurück, ob die Wärmepumpe gerade eingeschaltet ist."""
        return self.power == "1"


class CFGroupAsyncClient:
    """Asynchroner Wrapper um die Cloud-API für Home Assistant."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        cloud_url: str = DEFAULT_CLOUD_URL,
        app_id: str = DEFAULT_APP_ID,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._cloud_url = cloud_url.rstrip("/")
        self._app_id = app_id
        self._timeout = ClientTimeout(total=timeout)
        self._token: str | None = None
        self._token_created_at: float | None = None

    async def async_login(self) -> None:
        """Meldet sich an der Cloud an und speichert den Token."""
        password_hash = md5(self._password.encode("utf-8")).hexdigest()
        payload = {
            "password": password_hash,
            "loginSource": "IOS",
            "areaCode": "en",
            "appId": self._app_id,
            "type": "2",
            "userName": self._username,
        }
        response = await self._async_request("user/login", payload, include_token=False)
        token = response.get("objectResult", {}).get("x-token")

        if not token:
            raise CFGroupAuthenticationError(
                "Die Cloud hat keinen gültigen API-Token zurückgegeben."
            )

        self._token = str(token)
        self._token_created_at = monotonic()

    async def async_ensure_token(self) -> None:
        """Sorgt dafür, dass ein gültiger Token vorhanden ist."""
        if self._token is None or self._token_created_at is None:
            await self.async_login()
            return

        if monotonic() - self._token_created_at > TOKEN_RENEWAL_SECONDS:
            await self.async_login()

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Holt die Liste aller Geräte des Nutzers."""
        await self.async_ensure_token()
        response = await self._async_request("device/deviceList", {})
        devices = response.get("objectResult")

        if not isinstance(devices, list):
            raise CFGroupResponseError(
                "Die Cloud hat eine ungültige Geräteliste zurückgegeben."
            )

        return devices

    async def async_get_first_device_code(self) -> str:
        """Gibt den device_code des ersten Gerätes zurück."""
        devices = await self.async_get_devices()
        if not devices:
            raise CFGroupResponseError(
                "Die Cloud meldet keine Geräte für diesen Account."
            )

        device_code = devices[0].get("device_code")
        if not device_code:
            raise CFGroupResponseError(
                "Das erste Gerät enthält keinen device_code."
            )

        return str(device_code)

    async def async_get_heatpump_data(self, device_code: str) -> HeatPumpData:
        """Holt aufbereitete Messwerte für das angegebene Gerät."""
        await self.async_ensure_token()
        payload = {
            "deviceCode": device_code,
            "appId": self._app_id,
            "protocalCodes": list(POLLED_PROTOCOL_CODES),
        }
        response = await self._async_request("device/getDataByCode", payload)
        object_result = response.get("objectResult")

        if not isinstance(object_result, list):
            raise CFGroupResponseError(
                "Die Cloud hat ungültige Gerätedaten zurückgegeben."
            )

        values: dict[str, Any] = {}
        for item in object_result:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            if code is None:
                continue
            values[str(code)] = item.get("value")

        return HeatPumpData(
            power=_to_optional_string(values.get("Power")),
            mode=_to_optional_string(values.get("Mode")),
            mode_state=_to_optional_string(values.get("ModeState")),
            inlet_temperature=_to_optional_float(values.get("T02")),
            coil_temperature=_to_optional_float(values.get("T04")),
            ambient_temperature=_to_optional_float(values.get("T05")),
            target_temperature=_to_optional_float(values.get("R01")),
            min_temperature=_to_optional_float(values.get("R04")),
            max_temperature=_to_optional_float(values.get("R05")),
            raw_values=values,
        )

    async def async_set_power(self, device_code: str, enabled: bool) -> None:
        """Schaltet die Wärmepumpe ein oder aus."""
        value = "1" if enabled else "0"
        await self._async_set_protocol_value(device_code, PROTOCOL_CODE_POWER, value)

    async def async_set_target_temperature(
        self,
        device_code: str,
        temperature: float,
    ) -> None:
        """Setzt die Zieltemperatur der Wärmepumpe."""
        await self._async_set_protocol_value(
            device_code,
            PROTOCOL_CODE_TARGET_TEMP,
            _format_number(temperature),
        )

    async def _async_set_protocol_value(
        self,
        device_code: str,
        protocol_code: str,
        value: str,
    ) -> None:
        """Sendet einen Steuerbefehl an die Cloud."""
        await self.async_ensure_token()
        payload = {
            "appId": self._app_id,
            "param": [
                {
                    "deviceCode": device_code,
                    "protocolCode": protocol_code,
                    "value": value,
                }
            ],
        }
        await self._async_request("device/control", payload)

    async def _async_request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        include_token: bool = True,
    ) -> dict[str, Any]:
        """Führt einen POST-Request gegen die Cloud-API aus."""
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if include_token and self._token:
            headers["x-token"] = self._token

        url = f"{self._cloud_url}/{endpoint}?lang=en"

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            ) as response:
                response.raise_for_status()
                try:
                    data = await response.json(content_type=None)
                except ValueError as error:
                    raise CFGroupResponseError(
                        "Die Cloud-Antwort ist kein gültiges JSON."
                    ) from error
        except ClientError as error:
            raise CFGroupConnectionError(
                f"Verbindung zur Cloud fehlgeschlagen: {error}"
            ) from error
        except TimeoutError as error:
            raise CFGroupConnectionError(
                "Zeitüberschreitung bei der Verbindung zur Cloud."
            ) from error

        if not isinstance(data, dict):
            raise CFGroupResponseError(
                "Die Cloud-Antwort hat ein unerwartetes Format."
            )

        self._raise_for_api_error(data)
        return data

    def _raise_for_api_error(self, data: dict[str, Any]) -> None:
        """Wirft passende Fehler, wenn die Cloud einen Fehlerstatus meldet."""
        # Die Cloud nutzt sowohl `isReusltSuc` (Tippfehler der API) als auch `isResultSuc`.
        is_success_flag = data.get("isReusltSuc", data.get("isResultSuc", True))
        if is_success_flag is False:
            message = (
                data.get("msg")
                or data.get("message")
                or "Die Cloud meldet einen unbekannten Fehler."
            )
            text = str(message).lower()
            if "token" in text or "auth" in text or "login" in text:
                self._token = None
                self._token_created_at = None
                raise CFGroupAuthenticationError(str(message))
            raise CFGroupResponseError(str(message))


def _to_optional_float(value: Any) -> float | None:
    """Konvertiert einen API-Wert in eine Gleitkommazahl oder None."""
    if value in (None, "", "null"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_string(value: Any) -> str | None:
    """Konvertiert einen API-Wert in einen String oder None."""
    if value in (None, "", "null"):
        return None
    return str(value)


def _format_number(value: float) -> str:
    """Formatiert eine Zahl möglichst kompakt für die Cloud-API."""
    if float(value).is_integer():
        return str(int(value))
    return str(value)
