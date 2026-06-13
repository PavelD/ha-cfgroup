# Changelog

All notable changes to this project will be documented in this file.

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
