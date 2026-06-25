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
CONF_MODEL_TYPE = "model_type"

# Unterstützte Modelle.
# TEP0001 – Nur Heizung (ursprünglich unterstütztes Modell, Standard/Fallback).
# TEP0004 – Heizen + Kühlen + Automatik.
MODEL_TEP0001 = "tep0001"
MODEL_TEP0004 = "tep0004"

# TEP0004 – Werte für den Protocol-Code "Mode".
MODE_COOLING = "0"
MODE_HEATING = "1"
MODE_AUTO = "2"

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
PROTOCOL_CODE_TARGET_TEMP = "R01"      # TEP0001: Zieltemperatur; TEP0004: Kühl-Sollwert
PROTOCOL_CODE_HEATING_TEMP = "R02"     # TEP0004: Heiz-Sollwert
PROTOCOL_CODE_AUTO_TEMP = "R03"        # TEP0004: Sollwert im Automatikmodus
PROTOCOL_CODE_MIN_TEMP = "R04"
PROTOCOL_CODE_MAX_TEMP = "R05"
PROTOCOL_CODE_INLET_TEMP = "T02"
PROTOCOL_CODE_COIL_TEMP = "T04"
PROTOCOL_CODE_AMBIENT_TEMP = "T05"

POLLED_PROTOCOL_CODES: tuple[str, ...] = (
    PROTOCOL_CODE_POWER,
    PROTOCOL_CODE_MODE,
    PROTOCOL_CODE_MODE_STATE,
    "State_power",
    "State_mode",
    "D01",
    "D02",
    "D03",
    "D04",
    "D05",
    "D06",
    "H01",
    "H02",
    "H03",
    "H04",
    "H05",
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T06",
    "Set_Temp",
    "H06",
    "H09",
    "P01",
    "P02",
    "P03",
    "P04",
    "O01",
    "O02",
    "O03",
    "O04",
    "S01",
    "S02",
    "S03",
    "Prog_Version",
    "Material_Code",
    PROTOCOL_CODE_TARGET_TEMP,
    PROTOCOL_CODE_HEATING_TEMP,
    PROTOCOL_CODE_AUTO_TEMP,
    PROTOCOL_CODE_MIN_TEMP,
    PROTOCOL_CODE_MAX_TEMP,
    "R06",
    "R07",
    # TEP0004 nutzt T1–T5 statt T01–T06 (ohne führende Null).
    "T1",
    "T2",
    "T3",
    "T4",
    "T5",
)

# Fallback-Grenzen, falls die Cloud keine Min/Max-Werte liefert.
# TEP0001: R04/R05 liefern echte Grenzwerte; diese werden nur als Notfall-Fallback genutzt.
FALLBACK_MIN_TEMP = 15.0
FALLBACK_MAX_TEMP = 40.0
# TEP0004: R04/R05 sind Differenzwerte (z. B. 0,5 °C Hysterese), keine Temperaturlimits.
# Die echten Grenzen kommen aus dem rangeStart/rangeEnd der R01–R03-Felder (12–40 °C).
FALLBACK_MIN_TEMP_TEP0004 = 12.0
FALLBACK_MAX_TEMP_TEP0004 = 40.0
TEMP_STEP = 0.5
