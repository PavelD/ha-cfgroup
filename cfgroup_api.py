from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from time import monotonic
from typing import Any

import requests


DEFAULT_CLOUD_URL = "https://cloud.linked-go.com:449/crmservice/api/app"
DEFAULT_APP_ID = "16"
DEFAULT_TOKEN_RENEWAL_SECONDS = 82_800
DEFAULT_PROTOCOL_CODES = (
    "Power",
    "Mode",
    "ModeState",
    "T02",
    "T03",
    "T04",
    "T05",
    "Set_Temp",
    "H06",
    "R01",
    "R04",
    "R05",
)


class CFGroupApiError(Exception):
    pass


class CFGroupAuthenticationError(CFGroupApiError):
    pass


class CFGroupConnectionError(CFGroupApiError):
    pass


class CFGroupResponseError(CFGroupApiError):
    pass


@dataclass(frozen=True)
class HeatPumpData:
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
        return self.power == "1"

    @property
    def thermostat_mode(self) -> str:
        if self.is_on:
            return "heat"
        return "off"


class CFGroupApiClient:
    def __init__(
        self,
        username: str,
        password: str,
        cloud_url: str = DEFAULT_CLOUD_URL,
        app_id: str = DEFAULT_APP_ID,
        token_renewal_seconds: int = DEFAULT_TOKEN_RENEWAL_SECONDS,
        timeout: int = 15,
    ) -> None:
        self.username = username
        self.password = password
        self.cloud_url = cloud_url.rstrip("/")
        self.app_id = app_id
        self.token_renewal_seconds = token_renewal_seconds
        self.timeout = timeout
        self._token: str | None = None
        self._token_created_at: float | None = None
        self._session = requests.Session()

    def login(self) -> None:
        password_hash = md5(self.password.encode("utf-8")).hexdigest()
        payload = {
            "password": password_hash,
            "loginSource": "IOS",
            "areaCode": "en",
            "appId": self.app_id,
            "type": "2",
            "userName": self.username,
        }
        response = self._request("user/login", payload, include_token=False)
        token = response.get("objectResult", {}).get("x-token")

        if not token:
            raise CFGroupAuthenticationError("API-Token konnte nicht abgerufen werden.")

        self._token = str(token)
        self._token_created_at = monotonic()

    def ensure_token(self) -> None:
        if self._token is None or self._token_created_at is None:
            self.login()
            return

        token_age = monotonic() - self._token_created_at
        if token_age > self.token_renewal_seconds:
            self.login()

    def get_devices(self) -> list[dict[str, Any]]:
        self.ensure_token()
        response = self._request("device/deviceList", {})
        devices = response.get("objectResult")

        if not isinstance(devices, list):
            raise CFGroupResponseError("Die Geräteliste der API hat ein unerwartetes Format.")

        return devices

    def get_first_device_code(self) -> str:
        devices = self.get_devices()
        if not devices:
            raise CFGroupResponseError("Die API hat keine Geräte zurückgegeben.")

        device_code = devices[0].get("device_code")
        if not device_code:
            raise CFGroupResponseError("Das erste Gerät enthält keinen device_code.")

        return str(device_code)

    def get_data_by_code(
        self,
        device_code: str,
        protocol_codes: tuple[str, ...] = DEFAULT_PROTOCOL_CODES,
    ) -> HeatPumpData:
        self.ensure_token()
        payload = {
            "deviceCode": device_code,
            "appId": self.app_id,
            "protocalCodes": list(protocol_codes),
        }
        response = self._request("device/getDataByCode", payload)
        object_result = response.get("objectResult")

        if not isinstance(object_result, list):
            raise CFGroupResponseError("Die Gerätedaten der API haben ein unerwartetes Format.")

        values = {
            str(item.get("code")): item.get("value")
            for item in object_result
            if isinstance(item, dict) and item.get("code") is not None
        }

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

    def set_power(self, device_code: str, enabled: bool) -> dict[str, Any]:
        value = "1" if enabled else "0"
        return self.set_protocol_value(device_code, "Power", value)

    def set_target_temperature(self, device_code: str, temperature: float) -> dict[str, Any]:
        return self.set_protocol_value(device_code, "R01", _format_number(temperature))

    def set_protocol_value(
        self,
        device_code: str,
        protocol_code: str,
        value: str,
    ) -> dict[str, Any]:
        self.ensure_token()
        payload = {
            "appId": self.app_id,
            "param": [
                {
                    "deviceCode": device_code,
                    "protocolCode": protocol_code,
                    "value": value,
                }
            ],
        }
        return self._request("device/control", payload)

    def _request(
        self,
        endpoint: str,
        payload: dict[str, Any],
        include_token: bool = True,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if include_token and self._token:
            headers["x-token"] = self._token

        try:
            response = self._session.post(
                f"{self.cloud_url}/{endpoint}?lang=en",
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            raise CFGroupConnectionError(f"API-Anfrage fehlgeschlagen: {error}") from error

        try:
            data = response.json()
        except ValueError as error:
            raise CFGroupResponseError("Die API-Antwort ist kein gültiges JSON.") from error

        self._raise_for_api_error(data)
        return data

    def _raise_for_api_error(self, data: dict[str, Any]) -> None:
        if data.get("isReusltSuc") is False or data.get("isResultSuc") is False:
            message = data.get("msg") or data.get("message") or "Die API meldet einen Fehler."
            if "token" in str(message).lower() or "auth" in str(message).lower():
                self._token = None
                self._token_created_at = None
                raise CFGroupAuthenticationError(str(message))
            raise CFGroupResponseError(str(message))


def _to_optional_float(value: Any) -> float | None:
    if value in (None, "", "null"):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_optional_string(value: Any) -> str | None:
    if value in (None, "", "null"):
        return None
    return str(value)


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return str(value)
