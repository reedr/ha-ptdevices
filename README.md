# PTDevices (extended)

A drop-in replacement for Home Assistant's built-in **PTDevices** integration (tank level
monitors from ParemTech). It is the core integration from Home Assistant 2026.9.1, plus
entities for API fields that core leaves out.

Installed through HACS it overrides the built-in integration (same `ptdevices` domain). Your
existing config entry, devices and entity IDs are kept, because unique IDs are unchanged.
Home Assistant logs a warning that a custom integration overrides a core one; that's expected.
Remove it from HACS and restart to go back to the built-in version.

## Added entities (per device, when the API reports the field)

| Entity | From | Notes |
|---|---|---|
| Transmitter last reported | `tx_reported` | When the tank transmitter last sent a reading. The level is only as fresh as this. |
| Last reported | `reported` | When the receiver last checked in with the cloud (diagnostic). |
| Enclosure temperature | `enclosure_temperature` | In the account's temperature units (diagnostic). |
| Tank depth | `device_setup.depth` | As set up in the PTDevices app; feet on imperial accounts, metres otherwise (diagnostic). |
| Water depth | tank depth × level % | Same units as tank depth. |
| Volume | level % × capacity | Only for tanks given a capacity under **Configure**; gallons on US accounts, litres otherwise. |

The API reports times without a year, in UTC; the year is taken as the one that puts the time
just before now.

The device model now shows the hardware model (e.g. `PTLevelLongRange`), and the integration
has a diagnostics download with every field the API returns (account details redacted).

## Tank capacity

**Settings → Devices & services → PTDevices → Configure** lists each device. Enter a tank's full
capacity to add its Volume sensor; clear it to remove the sensor.

## Install

Add this repository to HACS as a custom repository (category: Integration), download
**PTDevices (extended)**, and restart Home Assistant.

## License

Apache-2.0, as the Home Assistant core code it is derived from. See `LICENSE.md`.
