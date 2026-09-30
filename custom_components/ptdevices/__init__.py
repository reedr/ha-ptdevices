"""The PTDevices integration."""

from aioptdevices.configuration import Configuration
from aioptdevices.interface import Interface

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_URL
from .coordinator import PTDevicesConfigEntry, PTDevicesCoordinator

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: PTDevicesConfigEntry
) -> bool:
    """Set up PTDevices from a config entry."""
    auth_token: str = config_entry.data[CONF_API_TOKEN]
    session = async_get_clientsession(hass)
    ptdevices_interface = Interface(
        Configuration(
            auth_token=auth_token,
            device_id="*",  # Retrieve data for all devices in account
            url=DEFAULT_URL,
            session=session,
        )
    )

    config_entry.runtime_data = coordinator = PTDevicesCoordinator(
        hass,
        config_entry,
        ptdevices_interface,
    )
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(config_entry, _PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(_async_update_options))

    return True


async def _async_update_options(hass: HomeAssistant, entry: PTDevicesConfigEntry) -> None:
    """Reload to add or remove capacity volume sensors."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: PTDevicesConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
