"""Fixtures for the PTDevices override tests."""

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from aioptdevices.interface import PTDevicesResponse, _format_data
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

pytest_plugins = ("pytest_homeassistant_custom_component",)

NOW = "2026-09-30 23:30:00+00:00"


@pytest.fixture(autouse=True)
def enable_override(enable_custom_integrations):
    """Load custom_components/ptdevices in place of the built-in integration."""


@pytest.fixture
def raw_devices() -> list[dict[str, Any]]:
    """The API's device list, as the server sends it."""
    return json.loads((Path(__file__).parent / "fixtures" / "devices.json").read_text())["data"]


@pytest.fixture
def mock_interface(raw_devices) -> Generator[AsyncMock]:
    """Serve the fixture through the library's own formatting."""
    with (
        patch("custom_components.ptdevices.Interface", autospec=True) as interface,
        patch("custom_components.ptdevices.config_flow.Interface", new=interface),
    ):
        interface.return_value.get_data.side_effect = lambda: PTDevicesResponse(
            code=200, body=_format_data(json.loads(json.dumps(raw_devices)))
        )
        yield interface.return_value


@pytest.fixture
def config_entry() -> MockConfigEntry:
    """A PTDevices account entry."""
    return MockConfigEntry(
        domain="ptdevices",
        title="Test User",
        data={CONF_API_TOKEN: "test-token"},
        unique_id="1234",
    )


async def setup_entry(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Add and set up the entry, on US units like the account."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
