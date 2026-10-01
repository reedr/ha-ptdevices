"""Diagnostics for PTDevices."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import PTDevicesConfigEntry

TO_REDACT = {
    CONF_API_TOKEN,
    "address",
    "delivery_notes",
    "device_id",
    "id",
    "lat",
    "lng",
    "local_ip",
    "share_id",
    "title",
    "unique_id",
    "user_email",
    "user_id",
    "user_name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PTDevicesConfigEntry
) -> dict[str, Any]:
    """Return the entry and every field the API returned for each device.

    Devices are listed in order rather than keyed by their MAC-based IDs.
    """
    entry_dict = entry.as_dict()
    options = dict(entry_dict.get("options") or {})
    if "capacities" in options:
        options["capacities"] = list(options["capacities"].values())
    entry_dict["options"] = options
    return {
        "entry": async_redact_data(entry_dict, TO_REDACT),
        "devices": [
            async_redact_data(device, TO_REDACT) for device in entry.runtime_data.data.values()
        ],
    }
