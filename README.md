# CF Group Heat Pump for Home Assistant

[English](README.md) · [Deutsch](README.de.md)

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/v/release/Afraskai/cfgroup?include_prereleases&sort=semver)](https://github.com/Afraskai/cfgroup/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  <img src="images/logo.svg" alt="Heat Pump Integration for Home Assistant" width="360">
</p>

Native Home Assistant integration for CF Group / Aquatemp heat pumps that are controlled through the Linked-Go cloud. Installable via HACS as a custom repository.

Manufacturer: [CF Group](https://www.cf.group/de/)

> **Disclaimer:** This is an **unofficial** community project and is **not affiliated with, endorsed by, or supported by CF Group, Aquatemp or Linked-Go**. All product names, logos and brands are property of their respective owners and are used here for identification purposes only. The integration relies on a public cloud API that may change or break at any time without notice.

## Features

- **Climate entity:** Heat pump exposed as a thermostat with `Heat`/`Off` and target temperature.
- **Sensors:** Inlet, coil, ambient and target temperature plus operating mode.
- **Switch:** Dedicated power switch.
- **Config flow:** Full setup through the Home Assistant UI.
- **Options flow:** Polling interval can be adjusted later.
- **Limits:** Minimum and maximum temperature are fetched from the cloud and honored when changing the target temperature.

## Requirements

- **Home Assistant:** 2024.12 or newer.
- **Cloud account:** Credentials for the CF Group / Aquatemp / Linked-Go app.
- **Internet connection:** The integration talks directly to the vendor cloud.

## Tested hardware

This integration has been developed and tested **only with the `CF Pool Heat Pump SMART PLUS 3 kW`**.

> ⚠️ **Important safety note:** The Linked-Go cloud is shared by many different heat-pump models, and vendors do **not** assign the technical codes (e.g. `R01`, `R04`, `Mode`, `Power`) consistently across models. On a different model the same code may have a completely different meaning or value range. Using this integration on a model other than the tested one **without verification** can therefore cause incorrect values to be written to the device — up to and including damage to the unit or safety hazards.
>
> **Before first use, please verify the meaning of the codes in the vendor app:**
>
> 1. Open the Aquatemp app and select your device.
> 2. Open `Device settings → Device parameters`.
> 3. Compare the codes shown under `Status parameters` (read-only values) and `Control parameters` (e.g. code `066`) with the values in the table below.
> 4. If `R01` (target temperature), `R04`/`R05` (min/max), `T02`/`T04`/`T05` (temperatures), `Power` and `Mode` do **not** match, **do not use** the integration with that device and please open an issue.

## Protocol codes

The cloud API uses technical codes. These are used internally by the integration. The table below applies to the `CF Pool Heat Pump SMART PLUS 3 kW` and may differ on other models (see [Tested hardware](#tested-hardware)):

### Temperatures

- **`R01`:** Target temperature.
- **`R04`:** Minimum heating temperature.
- **`R05`:** Maximum heating temperature.
- **`T02`:** Inlet temperature.
- **`T04`:** Coil temperature.
- **`T05`:** Ambient temperature.

### Control

- **`Power`:** On/Off, where `0` means off and `1` means on.
- **`Mode`:** Operating mode.
- **`ModeState`:** Status of the current operating mode.

## Installation

### Via HACS (recommended)

1. Open HACS and choose `Custom repositories` in the top-right menu.
2. Enter the repository URL, select category `Integration` and add it.
3. Install `CF Group Heat Pump` from HACS.
4. Restart Home Assistant.
5. Open `Settings → Devices & services → Add integration` and search for `CF Group Heat Pump`.

### Manual installation

1. Copy the folder `custom_components/cfgroup_heatpump` into your Home Assistant config directory at `config/custom_components/cfgroup_heatpump`.
2. Restart Home Assistant.
3. `Settings → Devices & services → Add integration` → `CF Group Heat Pump`.

## Setup

The setup dialog asks for:

- **Username / e-mail:** Same as in the Aquatemp / Linked-Go app.
- **Password:** Same as in the app.
- **Cloud URL:** Only change if needed, the default usually works.

Later, the polling interval can be changed under `Settings → Devices & services → CF Group Heat Pump → Configure`. The minimum is 60 seconds to be gentle on the cloud API.

## Development and testing

Automated tests run with `pytest` directly against the cloud client (no Home Assistant stack required). They cover error handling, the automatic re-login flow and the new diagnostic endpoints.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests/
```

## Project layout

```text
custom_components/
  cfgroup_heatpump/
    __init__.py        Integration setup
    manifest.json      HA metadata
    const.py           Domain and protocol codes
    api.py             Async cloud client
    coordinator.py     DataUpdateCoordinator (with offline tolerance)
    config_flow.py     UI setup + options flow
    entity.py          Shared CoordinatorEntity base
    climate.py         Thermostat
    sensor.py          Temperatures, mode, cloud status (diagnostic)
    binary_sensor.py   Fault sensor (diagnostic)
    switch.py          Power switch
    strings.json       UI strings
    translations/
      de.json
      en.json
tests/                 pytest suite against the cloud client
hacs.json              HACS metadata
requirements-dev.txt   Development dependencies (pytest, aiohttp)
```

## Legacy bash/MQTT variant

An earlier bash/MQTT implementation (`api_cfgroup.sh` with `config.sh`) is kept only in a local `archive/` folder. That folder is ignored via `.gitignore` and is not pushed to GitHub.

## Troubleshooting

- **Login fails:** Verify username and password using the vendor app.
- **Cloud not reachable:** Check the Home Assistant host's internet connection.
- **No device found:** The account must have at least one registered heat pump.
- **Logs:** Open `Settings → System → Logs` and filter for `cfgroup_heatpump`.

## License and warranty

This project is licensed under the **MIT License**. See [`LICENSE`](LICENSE) for the full text.

The software is provided **"as is", without warranty of any kind**, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages or other liability arising from the use of this software.

Use at your own risk. Operating a heat pump outside of the manufacturer's recommended parameters may damage the device, void warranty or cause safety issues. Always follow the manufacturer's documentation.
