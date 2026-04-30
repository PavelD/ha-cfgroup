import os
from getpass import getpass

from cfgroup_api import CFGroupApiClient, CFGroupApiError, DEFAULT_CLOUD_URL


def main() -> int:
    username = os.getenv("CFGROUP_USERNAME") or input("CF Group Benutzername: ").strip()
    password = os.getenv("CFGROUP_PASSWORD") or getpass("CF Group Passwort: ")
    cloud_url = os.getenv("CFGROUP_CLOUD_URL", DEFAULT_CLOUD_URL)

    client = CFGroupApiClient(
        username=username,
        password=password,
        cloud_url=cloud_url,
    )

    try:
        client.login()
        device_code = client.get_first_device_code()
        heatpump_data = client.get_data_by_code(device_code)
    except CFGroupApiError as error:
        print(f"Fehler: {error}")
        return 1

    print(f"Gerät: {device_code}")
    print(f"Power: {heatpump_data.power}")
    print(f"Thermostat-Modus: {heatpump_data.thermostat_mode}")
    print(f"Modus: {heatpump_data.mode}")
    print(f"Einlass-Temperatur: {heatpump_data.inlet_temperature} °C")
    print(f"Coil-Temperatur: {heatpump_data.coil_temperature} °C")
    print(f"Umgebungstemperatur: {heatpump_data.ambient_temperature} °C")
    print(f"Zieltemperatur: {heatpump_data.target_temperature} °C")
    print(f"Min. Temperatur: {heatpump_data.min_temperature} °C")
    print(f"Max. Temperatur: {heatpump_data.max_temperature} °C")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
