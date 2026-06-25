# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **TEP0004 model support**: heating / cooling / auto heat pumps are now supported via a new model selection in the config flow
  - Climate entity exposes `Heat`, `Cool`, `Auto` (`heat_cool`) and `Off` modes
  - Per-mode setpoints: cooling → R01, heating → R02, auto → R03
  - `hvac_action` reports `heating`, `cooling`, `defrosting` or `idle` based on `State_mode`
- **Return air temperature sensor** (TEP0004 only): new sensor reading protocol code `T1`
- **Cooling state** added to the operating state sensor (`state_mode`): new value `cooling`
- **Model selector** in setup and reconfigure dialogs: `TEP0001 – Heating only` or `TEP0004 – Heating / Cooling / Auto`
- **Transparent sensor code fallback**: temperature sensors now try both `T02`-style (TEP0001) and `T2`-style (TEP0004) protocol codes automatically

### Backward compatibility
- Existing TEP0001 setups are unaffected; `model_type` defaults to `tep0001` when absent from the config entry

## [0.5.1] - 2026-06-13

### Added
- **Idle detection**: climate entity (`hvac_action`) now reports `idle` instead of `heating` when the target temperature is reached — the thermostat correctly shows the idle state (no orange ring) when the pump is on but not actively heating
- **Operating state sensor**: new state `idle` is shown when the pump is on but target temperature is reached or `State_mode` is unknown

### Translations
- German: `idle` → `Leerlauf`
- English: `idle` → `Idle`

## [0.5.0] - 2026-06-13

### Added
- **`hvac_action` property**: climate entity now reports `heating` / `defrosting` / `idle` / `off` to HomeAssistant — the thermostat card shows the coloured heating indicator (orange ring) when the heat pump is actively heating

## [0.4.0] - 2026-05-17

### Added
- **Defrost sensor** (`binary_sensor`): detects active defrost cycle via `State_mode = 17` — shown as diagnostic entity "Abtauung / Defrost"
- **Outlet temperature sensor** (`T03`): return water temperature (Rücklauftemperatur)
- **Exhaust temperature sensor** (`T06`): exhaust / hot-gas temperature (Abluftemperatur)
- **Operating state sensor** (`State_mode`): enum sensor showing current operating state (`heating` / `defrost`) as diagnostic entity

### Fixed
- Fault code parsing: the cloud API returns `faultCode` (camelCase), which was not recognized — active fault codes (e.g. `E03`) are now correctly read and exposed as `active_faults` attribute on the fault binary sensor

### Changed
- Extended list of polled protocol codes (`const.py`) to include all known status and control parameters

## [0.3.0] - 2026-05-15

### Added
- Cloud status sensor (`ONLINE` / `OFFLINE`) as diagnostic entity
- Fault binary sensor with `active_faults` attribute (code + description)
- Fault data fetched via `device/getFaultDataByDeviceCode`
- Re-authentication flow when cloud credentials expire
- Reconfigure flow to change credentials or cloud URL without re-setup
- `getDeviceStatus` pre-check to skip expensive data query when device is offline

### Changed
- Hardened cloud client with automatic token renewal and retry on `401`
- Up to 3 consecutive update failures tolerated before entities go unavailable

## [0.2.0] - 2026-04-01

### Added
- Options flow: polling interval configurable after setup
- Minimum and maximum temperature fetched from cloud and enforced in climate entity

### Fixed
- Token renewal interval corrected

## [0.1.0] - 2026-03-15

### Added
- Initial release
- Climate entity (heat / off, target temperature)
- Sensors: inlet temperature, coil temperature, ambient temperature
- Power switch
- Config flow (username, password, cloud URL)
