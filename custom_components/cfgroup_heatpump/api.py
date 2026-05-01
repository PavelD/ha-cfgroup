"""Asynchroner Client für die CF Group / Linked-Go Cloud-API."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import md5
from time import monotonic
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession, ClientTimeout

from .const import (
    DEFAULT_APP_ID,
    DEFAULT_CLOUD_URL,
    ERROR_CODE_SUCCESS,
    ERROR_CODE_TOKEN_INVALID,
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


# Statuswert, den die Cloud im Feld `status` von `getDeviceStatus` zurückgibt,
# wenn das Gerät online ist. Alle anderen Werte (z. B. "OFFLINE") werden als
# offline interpretiert.
DEVICE_STATUS_ONLINE = "ONLINE"


@dataclass(frozen=True)
class DeviceStatus:
    """Roher Online-/Fehler-Status eines Gerätes laut Cloud."""

    status: str | None
    is_fault: bool
    raw: dict[str, Any]

    @property
    def is_online(self) -> bool:
        """Gibt True zurück, wenn die Cloud das Gerät als online führt."""
        return self.status == DEVICE_STATUS_ONLINE


@dataclass(frozen=True)
class FaultEntry:
    """Ein einzelner aktiver Fehler der Wärmepumpe.

    Das Schema ist von der Cloud nicht dokumentiert; wir halten daher die
    Rohdaten vor und stellen optional erkannte Felder zur Verfügung. Sollte
    ein Feld in der Antwort fehlen, bleibt es `None`.
    """

    code: str | None
    description: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class HeatPumpData:
    """Aufbereitete Messwerte einer Wärmepumpe.

    Neben den Sensorwerten aus `getDataByCode` enthält die Datenklasse
    optional auch den schlanken Geräte-Status (`getDeviceStatus`) und die
    aktiven Fehler (`getFaultDataByDeviceCode`). Beide Felder haben sichere
    Defaults, sodass Tests und ältere Code-Pfade unverändert funktionieren.
    """

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
    device_status: DeviceStatus | None = None
    faults: tuple[FaultEntry, ...] = ()

    @classmethod
    def empty(
        cls,
        device_status: "DeviceStatus | None" = None,
        faults: "tuple[FaultEntry, ...]" = (),
    ) -> "HeatPumpData":
        """Liefert einen leeren Datensatz, optional mit Status/Faults befüllt.

        Wird vom Coordinator beim ersten Update verwendet, wenn die Pumpe
        offline ist und somit kein `getDataByCode`-Ergebnis vorliegt. So
        können Diagnose-Entitäten trotzdem den aktuellen Status anzeigen,
        während Climate/Switch sauber als "nicht verfügbar" erscheinen.
        """
        return cls(
            power=None,
            mode=None,
            mode_state=None,
            inlet_temperature=None,
            coil_temperature=None,
            ambient_temperature=None,
            target_temperature=None,
            min_temperature=None,
            max_temperature=None,
            raw_values={},
            device_status=device_status,
            faults=faults,
        )

    @property
    def is_on(self) -> bool:
        """Gibt zurück, ob die Wärmepumpe gerade eingeschaltet ist."""
        return self.power == "1"

    @property
    def has_fault(self) -> bool:
        """True, wenn die Cloud aktive Fehler oder das `is_fault`-Flag meldet."""
        if self.device_status is not None and self.device_status.is_fault:
            return True
        return bool(self.faults)


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

    async def async_get_device_status(self, device_code: str) -> DeviceStatus:
        """Holt den schlanken Online-/Fehler-Status für ein Gerät.

        Nutzt den Endpoint `device/getDeviceStatus`, der deutlich weniger
        Daten als `getDataByCode` liefert und sich daher als günstiger
        Vorab-Check eignet (z. B. um bei einer offline gemeldeten Pumpe
        gar nicht erst die teurere Datenabfrage auszulösen).
        """
        await self.async_ensure_token()
        response = await self._async_request(
            "device/getDeviceStatus", {"deviceCode": device_code}
        )
        result = response.get("objectResult")
        if not isinstance(result, dict):
            raise CFGroupResponseError(
                "Die Cloud hat keinen gültigen Geräte-Status zurückgegeben."
            )

        status = _to_optional_string(result.get("status"))
        # Cloud spiegelt das Feld in beiden Schreibweisen; wir akzeptieren
        # beide und werten alles, was nicht explizit False ist, als Fehler.
        is_fault_value = result.get("is_fault", result.get("isFault", False))
        return DeviceStatus(
            status=status,
            is_fault=bool(is_fault_value),
            raw=result,
        )

    async def async_get_fault_data(self, device_code: str) -> list[FaultEntry]:
        """Holt die Liste aktiver Fehler für ein Gerät.

        Bei einer fehlerfreien Pumpe ist die Liste leer (`objectResult: []`).
        Das genaue Schema einzelner Einträge ist von der Cloud nicht
        dokumentiert; wir lesen daher robust die häufig genutzten Felder
        und legen die Rohdaten unter `raw` ab.
        """
        await self.async_ensure_token()
        response = await self._async_request(
            "device/getFaultDataByDeviceCode", {"deviceCode": device_code}
        )
        result = response.get("objectResult")
        if result is None:
            return []
        if not isinstance(result, list):
            raise CFGroupResponseError(
                "Die Cloud hat keine gültige Fehlerliste zurückgegeben."
            )

        faults: list[FaultEntry] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            faults.append(
                FaultEntry(
                    code=_to_optional_string(
                        item.get("fault_code")
                        or item.get("code")
                        or item.get("error_code")
                    ),
                    description=_to_optional_string(
                        item.get("description")
                        or item.get("fault_describe")
                        or item.get("error_msg")
                    ),
                    raw=item,
                )
            )
        return faults

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
        _retry_after_relogin: bool = True,
    ) -> dict[str, Any]:
        """Führt einen POST-Request gegen die Cloud-API aus.

        Bei Auth-Fehlern (egal ob HTTP 401/403 oder JSON-Body mit
        `error_code: "-100"`) wird der Token verworfen, ein frischer Login
        ausgelöst und der Request einmalig wiederholt. Damit erholt sich
        die Integration ohne manuelles "Neu laden" durch den Nutzer.
        Beim `user/login`-Endpunkt selbst wird kein Retry versucht, um
        Endlosschleifen zu verhindern.
        """
        try:
            return await self._async_send_once(endpoint, payload, include_token)
        except CFGroupAuthenticationError:
            if _retry_after_relogin and include_token and endpoint != "user/login":
                await self.async_login()
                return await self._async_request(
                    endpoint,
                    payload,
                    include_token=include_token,
                    _retry_after_relogin=False,
                )
            raise

    async def _async_send_once(
        self,
        endpoint: str,
        payload: dict[str, Any],
        include_token: bool,
    ) -> dict[str, Any]:
        """Sendet genau einen Request und wertet die Antwort aus."""
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
                # HTTP 401/403: Cloud lehnt den Request auf Transport-Ebene ab.
                # Das ist ein klares Auth-Signal, kein generischer Verbindungsfehler.
                if response.status in (401, 403):
                    self._invalidate_token()
                    raise CFGroupAuthenticationError(
                        f"Cloud lehnt Anfrage mit HTTP {response.status} ab."
                    )
                response.raise_for_status()
                try:
                    data = await response.json(content_type=None)
                except ValueError as error:
                    raise CFGroupResponseError(
                        "Die Cloud-Antwort ist kein gültiges JSON."
                    ) from error
        except ClientResponseError as error:
            # Wird von raise_for_status() ausgelöst (HTTP 4xx/5xx ungleich 401/403).
            raise CFGroupConnectionError(
                f"Cloud antwortet mit HTTP-Fehler {error.status}."
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

    def _invalidate_token(self) -> None:
        """Verwirft den aktuell gespeicherten Token."""
        self._token = None
        self._token_created_at = None

    def _raise_for_api_error(self, data: dict[str, Any]) -> None:
        """Wirft passende Fehler, wenn die Cloud einen Fehlerstatus meldet.

        Die Cloud signalisiert Fehler primär über das Feld `error_code`
        (String). `"0"` heißt Erfolg, alle anderen Werte sind Fehler. Das
        Flag `isReusltSuc` (Tippfehler der API) bzw. `isResultSuc` ist ein
        zusätzliches Bool, das bei Fehlern auf False steht.
        """
        error_code = data.get("error_code")
        if error_code is not None:
            error_code = str(error_code)

        is_success_flag = data.get("isReusltSuc", data.get("isResultSuc", True))
        is_error = (error_code is not None and error_code != ERROR_CODE_SUCCESS) or (
            is_success_flag is False
        )
        if not is_error:
            return

        message = (
            data.get("error_msg")
            or data.get("msg")
            or data.get("message")
            or "Die Cloud meldet einen unbekannten Fehler."
        )
        message_str = str(message)

        if error_code == ERROR_CODE_TOKEN_INVALID or _looks_like_auth_error(message_str):
            self._invalidate_token()
            raise CFGroupAuthenticationError(
                f"Cloud meldet Auth-Fehler (error_code={error_code}): {message_str}"
            )

        suffix = f" (error_code={error_code})" if error_code else ""
        raise CFGroupResponseError(f"{message_str}{suffix}")


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


def _looks_like_auth_error(message: str) -> bool:
    """Heuristische Erkennung von Auth-Meldungen als Fallback.

    Die Cloud liefert die Token-abgelaufen-Meldung auf Chinesisch
    ("请重新登录"). Wir prüfen daher zusätzlich auf das chinesische
    Schlüsselwort sowie auf die englischen/deutschen Varianten, falls die
    API in einer anderen Sprache antwortet.
    """
    text = message.lower()
    if any(keyword in text for keyword in ("token", "auth", "login", "anmelden")):
        return True
    # "请重新登录" = bitte neu einloggen.
    return "重新登录" in message or "登录" in message
