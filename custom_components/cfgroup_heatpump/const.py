"""Konstanten für die CF Group Wärmepumpen-Integration."""

from __future__ import annotations

DOMAIN = "cfgroup_heatpump"
MANUFACTURER = "CF Group"
MODEL = "Aquatemp"
MANUFACTURER_URL = "https://www.cf.group/de/"

DEFAULT_CLOUD_URL = "https://cloud.linked-go.com:449/crmservice/api/app"
DEFAULT_APP_ID = "16"

# Home Assistant speichert die Login-Daten im ConfigEntry unter diesen Schlüsseln.
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CLOUD_URL = "cloud_url"
CONF_UPDATE_INTERVAL = "update_interval"

# Abfrage-Intervall in Sekunden. 180 Sekunden schonen die Cloud-API.
DEFAULT_UPDATE_INTERVAL = 180
MIN_UPDATE_INTERVAL = 60

# Nach dieser Zeit wird der Login-Token vorsorglich erneuert.
TOKEN_RENEWAL_SECONDS = 82_800

# Cloud-Fehlercodes (Feld `error_code` in der JSON-Antwort).
ERROR_CODE_SUCCESS = "0"
ERROR_CODE_TOKEN_INVALID = "-100"  # Antwort enthält dann "请重新登录" (bitte neu einloggen).

# So viele aufeinanderfolgende fehlgeschlagene Polls darf der Coordinator
# tolerieren, bevor er die Entitäten als nicht verfügbar markiert. Bei
# kurzen Aussetzern (z. B. WP nachts stromlos) bleiben die letzten Werte
# erhalten und die Integration heilt sich beim nächsten Erfolg selbst.
MAX_FAILED_UPDATES_BEFORE_UNAVAILABLE = 3

# Protokoll-Codes der Cloud-API, die regelmäßig abgerufen werden.
PROTOCOL_CODE_POWER = "Power"
PROTOCOL_CODE_MODE = "Mode"
PROTOCOL_CODE_MODE_STATE = "ModeState"
PROTOCOL_CODE_TARGET_TEMP = "R01"
PROTOCOL_CODE_MIN_TEMP = "R04"
PROTOCOL_CODE_MAX_TEMP = "R05"
PROTOCOL_CODE_INLET_TEMP = "T02"
PROTOCOL_CODE_COIL_TEMP = "T04"
PROTOCOL_CODE_AMBIENT_TEMP = "T05"

POLLED_PROTOCOL_CODES: tuple[str, ...] = (
    PROTOCOL_CODE_POWER,
    PROTOCOL_CODE_MODE,
    PROTOCOL_CODE_MODE_STATE,
    "T02",
    "T03",
    "T04",
    "T05",
    "Set_Temp",
    "H06",
    PROTOCOL_CODE_TARGET_TEMP,
    PROTOCOL_CODE_MIN_TEMP,
    PROTOCOL_CODE_MAX_TEMP,
)

# Fallback-Grenzen, falls die Cloud keine Min/Max-Werte liefert.
FALLBACK_MIN_TEMP = 15.0
FALLBACK_MAX_TEMP = 40.0
TEMP_STEP = 0.5
