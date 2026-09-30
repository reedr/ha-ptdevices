"""Diagnostics for PTDevices."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant

from .coordinator import PTDevicesConfigEntry

TO_REDACT = {
    CONF_API_TOKEN,
    "user_email",
    "user_name",
    "user_id",
    "share_id",
    "lat",
    "lng",
    "address",
    "title",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PTDevicesConfigEntry
) -> dict[str, Any]:
    """Return the entry and every field the API returned for each device."""
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "devices": async_redact_data(entry.runtime_data.data, TO_REDACT),
    }
