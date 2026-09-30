"""Config flow for PTDevices integration."""

import logging
from typing import Any, override

import aioptdevices
import voluptuous as vol
from aioptdevices.configuration import Configuration
from aioptdevices.interface import Interface
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .const import CONF_CAPACITIES, DEFAULT_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

_CONF_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> tuple[str, str]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    session = async_get_clientsession(hass)
    ptdevices_interface = Interface(
        Configuration(
            auth_token=data[CONF_API_TOKEN],
            device_id="*",  # Retrieve data for all devices in account
            url=DEFAULT_URL,
            session=session,
        )
    )

    # Test Connection
    try:
        response = await ptdevices_interface.get_data()
    except aioptdevices.PTDevicesRequestError as err:
        raise CannotConnect from err

    except aioptdevices.PTDevicesUnauthorizedError as err:
        raise InvalidAuth from err

    body = response["body"]

    # Ensure the first device exists
    first_device = next(iter(body.values()), None)
    if first_device is None:
        raise NoDevicesFound

    user_name = first_device.get("user_name")
    user_id = first_device.get("user_id")

    title: str = str(user_name)
    unique_id: str = str(user_id)

    # Return title to be used for hub name
    return (title, unique_id)


class PTDevicesConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for PTDevices."""

    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Create the options flow."""
        return PTDevicesOptionsFlow()

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        errors: dict[str, str] = {}

        # Test connection when user data is available
        if user_input is not None:
            # Test connection
            try:
                title, unique_id = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_access_token"
            except NoDevicesFound:
                errors["base"] = "no_devices_found"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Connection Successful
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=title, data=user_input)

        # Show setup form
        return self.async_show_form(
            step_id="user", data_schema=_CONF_SCHEMA, errors=errors
        )


class PTDevicesOptionsFlow(OptionsFlow):
    """Set each tank's capacity, which adds a volume sensor."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """One capacity field per device, labelled with its name."""
        if self.config_entry.state is not ConfigEntryState.LOADED:
            return self.async_abort(reason="not_loaded")

        devices: dict[str, dict[str, Any]] = self.config_entry.runtime_data.data
        fields: dict[str, str] = {}
        for device_id, device in sorted(
            devices.items(), key=lambda item: str(item[1].get("title"))
        ):
            label = str(device.get("title") or device_id)
            if label in fields:
                label = f"{label} ({device_id})"
            fields[label] = device_id

        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_CAPACITIES: {
                        fields[label]: float(value)
                        for label, value in user_input.items()
                        if label in fields and value
                    }
                }
            )

        current: dict[str, float] = self.config_entry.options.get(CONF_CAPACITIES, {})
        selector = NumberSelector(
            NumberSelectorConfig(min=0, max=10_000_000, step=1, mode=NumberSelectorMode.BOX)
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        label, description={"suggested_value": current.get(device_id)}
                    ): selector
                    for label, device_id in fields.items()
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class NoDevicesFound(HomeAssistantError):
    """No devices were found in the account."""
