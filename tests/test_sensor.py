"""Sensors added by the override."""

from datetime import UTC, datetime

import pytest
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import UnitOfLength, UnitOfTemperature, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ptdevices.sensor import parse_reported

from .conftest import NOW, setup_entry


@pytest.mark.parametrize(
    ("text", "now", "expected"),
    [
        ("Sep 30th, 11:18 PM", "2026-09-30 23:30", datetime(2026, 9, 30, 23, 18, tzinfo=UTC)),
        ("Sep 1st, 12:05 AM", "2026-09-30 23:30", datetime(2026, 9, 1, 0, 5, tzinfo=UTC)),
        ("Oct 2nd, 12:30 PM", "2026-10-02 13:00", datetime(2026, 10, 2, 12, 30, tzinfo=UTC)),
        # Around new year the report can be from last year.
        ("Dec 31st, 11:59 PM", "2027-01-01 00:10", datetime(2026, 12, 31, 23, 59, tzinfo=UTC)),
        ("Jun 28th 2026, 6:08 PM", "2026-09-30 23:30", datetime(2026, 6, 28, 18, 8, tzinfo=UTC)),
        ("48 seconds ago", "2026-09-30 23:30", None),
        (None, "2026-09-30 23:30", None),
        ("Foo 3rd, 1:00 PM", "2026-09-30 23:30", None),
    ],
)
def test_parse_reported(text, now, expected) -> None:
    now_dt = datetime.fromisoformat(now).replace(tzinfo=UTC)
    assert parse_reported(text, now_dt) == expected


async def test_entities(
    hass: HomeAssistant,
    mock_interface,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)

    # Core's entities keep core's unique IDs.
    ent_reg = er.async_get(hass)
    assert ent_reg.async_get_entity_id("sensor", "ptdevices", "1234_AAAAAAAAAAA2_percent_level")
    assert hass.states.get("sensor.cistern_level_percent").state == "100"

    tx = hass.states.get("sensor.cistern_transmitter_last_reported")
    assert tx.state == "2026-09-30T21:42:00+00:00"
    assert hass.states.get("sensor.cistern_last_reported").state == "2026-09-30T23:17:00+00:00"

    temp = hass.states.get("sensor.ro_tanks_enclosure_temperature")
    assert float(temp.state) == pytest.approx(89.1, abs=0.1)
    assert temp.attributes["unit_of_measurement"] == UnitOfTemperature.FAHRENHEIT

    depth = hass.states.get("sensor.ro_tanks_tank_depth")
    assert float(depth.state) == pytest.approx(5.15)
    assert depth.attributes["unit_of_measurement"] == UnitOfLength.FEET
    assert float(hass.states.get("sensor.ro_tanks_water_depth").state) == pytest.approx(4.64)
    assert float(hass.states.get("sensor.cistern_water_depth").state) == pytest.approx(6.0)

    # No capacity set, no volume sensor.
    assert hass.states.get("sensor.cistern_volume") is None

    device = dr.async_get(hass).async_get_device_by_identifier(
        ("ptdevices", "1234_AAAAAAAAAAA2"), config_entry.entry_id
    )
    assert device.model == "PTLevelLongRange"


async def test_capacity_volume(
    hass: HomeAssistant,
    mock_interface,
    config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(NOW)
    await setup_entry(hass, config_entry)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["step_id"] == "init"
    assert set(result["data_schema"].schema) == {"RO Tanks", "Cistern"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"RO Tanks": 1000, "Cistern": 5250}
    )
    assert config_entry.options == {
        "capacities": {"AAAAAAAAAAA1": 1000.0, "AAAAAAAAAAA2": 5250.0}
    }
    await hass.async_block_till_done()

    volume = hass.states.get("sensor.ro_tanks_volume")
    assert volume.state == "900"
    assert volume.attributes["unit_of_measurement"] == UnitOfVolume.GALLONS
    assert hass.states.get("sensor.cistern_volume").state == "5250"
    assert er.async_get(hass).async_get_entity_id(
        "sensor", "ptdevices", "1234_AAAAAAAAAAA2_capacity_volume"
    )

    # Clearing a capacity removes its sensor on reload.
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    await hass.config_entries.options.async_configure(result["flow_id"], {"Cistern": 5250})
    await hass.async_block_till_done()
    assert config_entry.options == {"capacities": {"AAAAAAAAAAA2": 5250.0}}
    assert hass.states.get("sensor.cistern_volume").state == "5250"


async def test_diagnostics_redacts(
    hass: HomeAssistant, mock_interface, config_entry: MockConfigEntry
) -> None:
    from custom_components.ptdevices.diagnostics import async_get_config_entry_diagnostics

    await setup_entry(hass, config_entry)
    diag = await async_get_config_entry_diagnostics(hass, config_entry)
    assert diag["entry"]["data"]["api_token"] == "**REDACTED**"
    device = diag["devices"]["AAAAAAAAAAA2"]
    assert device["user_email"] == "**REDACTED**"
    assert device["tx_reported"] == "Sep 30th, 9:42 PM"
    assert device["power_y"] == 1122
