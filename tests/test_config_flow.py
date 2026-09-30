"""Setup flow (unchanged from core) still works through the override."""

from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(hass: HomeAssistant, mock_interface) -> None:
    result = await hass.config_entries.flow.async_init("ptdevices", context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_token": "test-token"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test User"
    assert result["result"].unique_id == "1234"
    await hass.async_block_till_done()
