"""Tests für die Fehlerbehandlung des Cloud-Clients.

Schwerpunkt: Regressionsabsicherung gegen den Bug, dass die Integration
nach einem abgelaufenen Token nicht ohne Reload wieder online kam.
Dazu prüfen wir das `error_code`-basierte Fehlerschema und den
automatischen Re-Login bei Auth-Fehlern.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest

from cfgroup_heatpump.api import (
    CFGroupAsyncClient,
    CFGroupAuthenticationError,
    CFGroupConnectionError,
    CFGroupResponseError,
    DeviceStatus,
    FaultEntry,
    HeatPumpData,
    _looks_like_auth_error,
)


# --------------------------------------------------------------------------- #
# Fake aiohttp ClientSession
# --------------------------------------------------------------------------- #

class _FakeResponse:
    """Minimaler Ersatz für aiohttp.ClientResponse für unsere Tests."""

    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: Any) -> bool:
        return False

    def raise_for_status(self) -> None:
        # 401/403 werden in api.py vor raise_for_status() abgefangen.
        if self.status >= 400:
            from aiohttp import ClientResponseError, RequestInfo
            from yarl import URL

            request_info = RequestInfo(URL("http://test"), "POST", {}, URL("http://test"))
            raise ClientResponseError(
                request_info=request_info,
                history=(),
                status=self.status,
                message="HTTP error",
            )

    async def json(self, content_type: str | None = None) -> Any:
        return self._payload


class _FakeSession:
    """Sammelt POST-Aufrufe und liefert vorab gesetzte Antworten."""

    def __init__(self) -> None:
        self._queue: list[tuple[int, Any]] = []
        self.calls: list[dict[str, Any]] = []

    def queue(self, status: int, payload: Any) -> None:
        self._queue.append((status, payload))

    def post(
        self,
        url: str,
        json: Any = None,
        headers: dict[str, str] | None = None,
        timeout: Any = None,
    ) -> _FakeResponse:
        self.calls.append(
            {"url": url, "json": json, "headers": dict(headers or {})}
        )
        if not self._queue:
            raise AssertionError(f"Unerwarteter Cloud-Aufruf: {url}")
        status, payload = self._queue.pop(0)
        return _FakeResponse(status, payload)


def _client(session: _FakeSession) -> CFGroupAsyncClient:
    return CFGroupAsyncClient(
        session=session,  # type: ignore[arg-type]
        username="user",
        password="pw",
    )


def _login_payload(token: str = "TOKEN") -> dict[str, Any]:
    return {
        "error_code": "0",
        "isReusltSuc": True,
        "objectResult": {"x-token": token},
    }


# --------------------------------------------------------------------------- #
# _raise_for_api_error
# --------------------------------------------------------------------------- #

def test_raise_for_api_error_success_does_nothing() -> None:
    client = _client(_FakeSession())
    # Sollte nicht werfen.
    client._raise_for_api_error(
        {"error_code": "0", "error_msg": "Success", "isReusltSuc": True}
    )


def test_raise_for_api_error_token_invalid_clears_token() -> None:
    client = _client(_FakeSession())
    client._token = "expired"
    client._token_created_at = 0.0

    # Antwortbild der Cloud bei abgelaufenem Token (chinesisch).
    payload = {
        "error_code": "-100",
        "error_msg": "请重新登录",
        "isReusltSuc": False,
        "objectResult": None,
    }

    with pytest.raises(CFGroupAuthenticationError):
        client._raise_for_api_error(payload)

    assert client._token is None
    assert client._token_created_at is None


def test_raise_for_api_error_generic_error_keeps_token() -> None:
    client = _client(_FakeSession())
    client._token = "still-valid"

    payload = {
        "error_code": "-1",
        "error_msg": "Get device error",
        "isReusltSuc": False,
    }

    with pytest.raises(CFGroupResponseError, match="Get device error"):
        client._raise_for_api_error(payload)

    # Bei einem fachlichen Fehler darf der Token NICHT verworfen werden.
    assert client._token == "still-valid"


def test_raise_for_api_error_legacy_message_match() -> None:
    """Auch ohne error_code muss eine englische Token-Meldung greifen."""
    client = _client(_FakeSession())
    client._token = "expired"

    payload = {"isReusltSuc": False, "msg": "Invalid token, please login again"}

    with pytest.raises(CFGroupAuthenticationError):
        client._raise_for_api_error(payload)

    assert client._token is None


# --------------------------------------------------------------------------- #
# _looks_like_auth_error
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "message",
    [
        "Token expired",
        "Please login again",
        "Authentication failed",
        "Bitte erneut anmelden",
        "请重新登录",  # chinesisch: bitte neu einloggen
        "登录已失效",
    ],
)
def test_looks_like_auth_error_positive(message: str) -> None:
    assert _looks_like_auth_error(message) is True


@pytest.mark.parametrize(
    "message",
    [
        "Get device error",
        "Internal server error",
        "",
        "Device offline",
    ],
)
def test_looks_like_auth_error_negative(message: str) -> None:
    assert _looks_like_auth_error(message) is False


# --------------------------------------------------------------------------- #
# Automatischer Re-Login (das Kern-Verhalten gegen den Reload-Bug)
# --------------------------------------------------------------------------- #

def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_request_retries_after_token_invalid_response() -> None:
    """Erster Call meldet Token-Ablauf, danach folgt Login + erfolgreicher Retry."""
    session = _FakeSession()

    # 1) Erster Versuch des fachlichen Calls: Token ist abgelaufen.
    session.queue(
        200,
        {
            "error_code": "-100",
            "error_msg": "请重新登录",
            "isReusltSuc": False,
        },
    )
    # 2) Automatischer Re-Login.
    session.queue(200, _login_payload(token="FRESH"))
    # 3) Wiederholung des fachlichen Calls mit frischem Token: Erfolg.
    success_payload = {
        "error_code": "0",
        "isReusltSuc": True,
        "objectResult": [{"code": "Power", "value": "1"}],
    }
    session.queue(200, success_payload)

    client = _client(session)
    client._token = "STALE"
    client._token_created_at = 0.0

    result = _run(client._async_request("device/getDataByCode", {"deviceCode": "X"}))

    assert result == success_payload
    assert client._token == "FRESH"

    # Genau drei Calls: ursprünglich, Login, Retry.
    assert len(session.calls) == 3
    assert session.calls[0]["headers"].get("x-token") == "STALE"
    assert "user/login" in session.calls[1]["url"]
    assert session.calls[2]["headers"].get("x-token") == "FRESH"


def test_request_does_not_retry_login_endpoint_itself() -> None:
    """Wenn schon der Login mit Auth-Fehler antwortet, kein zweiter Login-Versuch."""
    session = _FakeSession()
    session.queue(
        200,
        {
            "error_code": "-100",
            "error_msg": "请重新登录",
            "isReusltSuc": False,
        },
    )

    client = _client(session)

    with pytest.raises(CFGroupAuthenticationError):
        _run(client._async_request("user/login", {}, include_token=False))

    assert len(session.calls) == 1


def test_request_handles_http_401_as_auth_error() -> None:
    """HTTP 401 wird als Auth-Fehler gewertet, nicht als Verbindungsfehler."""
    session = _FakeSession()
    # 1) Erster Call: 401. 2) Re-Login. 3) Retry: Erfolg.
    session.queue(401, {})
    session.queue(200, _login_payload(token="NEW"))
    session.queue(200, {"error_code": "0", "isReusltSuc": True, "objectResult": []})

    client = _client(session)
    client._token = "OLD"
    client._token_created_at = 0.0

    result = _run(client._async_request("device/getDataByCode", {}))
    assert result["error_code"] == "0"
    assert client._token == "NEW"


# --------------------------------------------------------------------------- #
# Neue read-only Endpoints: getDeviceStatus, getFaultDataByDeviceCode
# Antwortbilder kommen 1:1 aus der Live-Probe gegen die Linked-Go-Cloud.
# --------------------------------------------------------------------------- #

def test_get_device_status_parses_online() -> None:
    """ONLINE-Status aus der Live-Cloud-Antwort wird sauber abgebildet."""
    session = _FakeSession()
    session.queue(
        200,
        {
            "error_code": "0",
            "isReusltSuc": True,
            "objectResult": {
                "is_fault": False,
                "isFault": False,
                "status": "ONLINE",
            },
        },
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    status = _run(client.async_get_device_status("AABBCCDDEEFF"))

    assert isinstance(status, DeviceStatus)
    assert status.status == "ONLINE"
    assert status.is_online is True
    assert status.is_fault is False
    # Rohdaten müssen für Diagnostik erhalten bleiben.
    assert status.raw["status"] == "ONLINE"


def test_get_device_status_offline_with_fault() -> None:
    session = _FakeSession()
    session.queue(
        200,
        {
            "error_code": "0",
            "isReusltSuc": True,
            "objectResult": {"is_fault": True, "status": "OFFLINE"},
        },
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    status = _run(client.async_get_device_status("X"))

    assert status.is_online is False
    assert status.is_fault is True


def test_get_device_status_invalid_payload_raises() -> None:
    """Wenn die Cloud kein objectResult-Dict liefert, klar fehlschlagen."""
    session = _FakeSession()
    session.queue(
        200,
        {"error_code": "0", "isReusltSuc": True, "objectResult": None},
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    with pytest.raises(CFGroupResponseError):
        _run(client.async_get_device_status("X"))


def test_get_fault_data_empty_returns_empty_list() -> None:
    """Pumpe ohne Fehler: Cloud liefert leere Liste, Methode ebenfalls."""
    session = _FakeSession()
    session.queue(
        200,
        {
            "error_code": "0",
            "isReusltSuc": True,
            "totalSize": 0,
            "objectResult": [],
        },
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    faults = _run(client.async_get_fault_data("AABBCCDDEEFF"))
    assert faults == []


def test_get_fault_data_parses_camelcase_fault_code() -> None:
    """Die echte Cloud-API liefert faultCode (camelCase) – muss erkannt werden."""
    session = _FakeSession()
    session.queue(
        200,
        {
            "error_code": "0",
            "isReusltSuc": True,
            "objectResult": [
                {
                    "faultCode": "E03",
                    "description": "Flow Switch Protection",
                    "errorLevel": 3,
                },
            ],
        },
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    faults = _run(client.async_get_fault_data("X"))

    assert len(faults) == 1
    assert faults[0].code == "E03"
    assert faults[0].description == "Flow Switch Protection"


def test_get_fault_data_parses_entries_robustly() -> None:
    """Unbekanntes Schema: häufige Feldnamen werden erkannt, Rest in raw."""
    session = _FakeSession()
    session.queue(
        200,
        {
            "error_code": "0",
            "isReusltSuc": True,
            "objectResult": [
                {"fault_code": "E03", "description": "High pressure"},
                {"code": "E07", "fault_describe": "Wassermangel"},
                # Unbekanntes Schema: trotzdem aufnehmen, raw bleibt erhalten.
                {"weird": "format", "id": 42},
                # Ungültiger Eintrag wird ignoriert.
                "kein-dict",
            ],
        },
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    faults = _run(client.async_get_fault_data("X"))

    assert len(faults) == 3
    assert isinstance(faults[0], FaultEntry)
    assert (faults[0].code, faults[0].description) == ("E03", "High pressure")
    assert (faults[1].code, faults[1].description) == ("E07", "Wassermangel")
    assert faults[2].code is None
    assert faults[2].description is None
    assert faults[2].raw == {"weird": "format", "id": 42}


# --------------------------------------------------------------------------- #
# HeatPumpData.empty / has_fault — Datenklassen-Verhalten
# --------------------------------------------------------------------------- #

def test_heatpump_data_empty_has_no_values() -> None:
    """Beim ersten Update offline soll `empty` saubere Defaults liefern."""
    status = DeviceStatus(status="OFFLINE", is_fault=False, raw={"status": "OFFLINE"})

    data = HeatPumpData.empty(device_status=status)

    # Sensorwerte alle leer ⇒ Climate/Sensoren werden "nicht verfügbar".
    assert data.power is None
    assert data.target_temperature is None
    assert data.inlet_temperature is None
    assert data.raw_values == {}

    # Diagnose-Felder gesetzt ⇒ Cloud-Status- und Störungs-Sensor funktionieren.
    assert data.device_status is status
    assert data.faults == ()
    assert data.is_on is False
    assert data.has_fault is False


def test_heatpump_data_empty_with_faults() -> None:
    fault = FaultEntry(code="E03", description="High pressure", raw={"code": "E03"})
    data = HeatPumpData.empty(faults=(fault,))

    assert data.faults == (fault,)
    assert data.has_fault is True


def test_has_fault_uses_device_status_flag() -> None:
    status = DeviceStatus(status="ONLINE", is_fault=True, raw={})
    data = HeatPumpData.empty(device_status=status)

    # Auch ohne Fault-Liste reicht das `is_fault`-Flag aus dem Status.
    assert data.faults == ()
    assert data.has_fault is True


def test_is_defrosting_uses_state_mode_17() -> None:
    data = HeatPumpData.empty()
    data.raw_values["State_mode"] = "17"

    assert data.is_defrosting is True


def test_is_defrosting_is_false_for_normal_heat_mode() -> None:
    data = HeatPumpData.empty()
    data.raw_values["State_mode"] = "1"

    assert data.is_defrosting is False


def test_get_fault_data_invalid_payload_raises() -> None:
    session = _FakeSession()
    session.queue(
        200,
        {"error_code": "0", "isReusltSuc": True, "objectResult": "nope"},
    )

    client = _client(session)
    client._token = "T"
    client._token_created_at = 0.0

    with pytest.raises(CFGroupResponseError):
        _run(client.async_get_fault_data("X"))


def test_request_propagates_connection_error_unchanged() -> None:
    """5xx-Fehler bleiben Verbindungsfehler und triggern keinen Re-Login."""
    session = _FakeSession()
    session.queue(503, {})

    client = _client(session)
    client._token = "VALID"
    client._token_created_at = 0.0

    with pytest.raises(CFGroupConnectionError):
        _run(client._async_request("device/getDataByCode", {}))

    # Genau ein Call: kein Re-Login-Versuch nach Verbindungsfehlern.
    assert len(session.calls) == 1
    assert client._token == "VALID"
