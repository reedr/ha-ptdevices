"""Constants for the PTDevices integration."""

DOMAIN = "ptdevices"
DEFAULT_URL = "https://api.ptdevices.com/token/v1"

# Options: tank capacity per device ID, in the account's volume units.
CONF_CAPACITIES = "capacities"
CONF_CAPACITY_UNIT = "capacity_unit"


def capacity_unit(options, devices) -> str:
    """The unit capacities are entered in: as saved, else from the account's units.

    Entries saved before the unit was stored used gallons on US accounts.
    """
    if unit := options.get(CONF_CAPACITY_UNIT):
        return unit
    us = any(d.get("units") == "US Imperial" for d in (devices or {}).values())
    return "gal" if us else "L"
