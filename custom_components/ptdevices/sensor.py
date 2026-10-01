"""Sensors for PTDevices device."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from string import ascii_letters
from typing import Any, cast, override

from aioptdevices.interface import PTDevicesStatusStates
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfElectricPotential,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import CONF_CAPACITIES, capacity_unit
from .coordinator import PTDevicesConfigEntry, PTDevicesCoordinator
from .entity import PTDevicesEntity

# Coordinator is used to centralize the data updates
PARALLEL_UPDATES = 0


class PTDevicesSensors(StrEnum):
    """Store keys for PTDevices sensors."""

    LEVEL_PERCENT = "percent_level"
    LEVEL_VOLUME = "volume_level"
    LEVEL_DEPTH = "depth_level"
    PROBE_TEMPERATURE = "probe_temperature"
    DEVICE_STATUS = "status"
    DEVICE_WIFI_STRENGTH = "wifi_signal"
    DEVICE_BATTERY_VOLTAGE = "battery_voltage"
    TX_SIGNAL_STRENGTH = "tx_signal"


@dataclass(kw_only=True, frozen=True)
class PTDevicesSensorEntityDescription(SensorEntityDescription):
    """Description for PTDevices sensor entities."""

    value_fn: Callable[[dict[str, str | int | float | None]], str | int | float | None]


SENSOR_DESCRIPTIONS: tuple[PTDevicesSensorEntityDescription, ...] = (
    # Percent of water in the tank
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.LEVEL_PERCENT,
        translation_key=PTDevicesSensors.LEVEL_PERCENT,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.LEVEL_PERCENT)),
    ),
    # Volume of water in the tank (Liters)
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.LEVEL_VOLUME,
        translation_key=PTDevicesSensors.LEVEL_VOLUME,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        device_class=SensorDeviceClass.VOLUME_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.LEVEL_VOLUME)),
    ),
    # Depth of water in the tank (Meters)
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.LEVEL_DEPTH,
        translation_key=PTDevicesSensors.LEVEL_DEPTH,
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.LEVEL_DEPTH)),
        suggested_display_precision=3,
    ),
    # Temperature measured by external temperature probe (Celsius)
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.PROBE_TEMPERATURE,
        translation_key=PTDevicesSensors.PROBE_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(float, data.get(PTDevicesSensors.PROBE_TEMPERATURE)),
    ),
    # Status of the device
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_STATUS,
        translation_key=PTDevicesSensors.DEVICE_STATUS,
        device_class=SensorDeviceClass.ENUM,
        options=[
            member.value
            for member in PTDevicesStatusStates
            if member.value != "unknown"
        ],
        value_fn=lambda data: (
            cast(str, data.get(PTDevicesSensors.DEVICE_STATUS))
            if cast(str, data.get(PTDevicesSensors.DEVICE_STATUS)) != "unknown"
            else None
        ),
    ),
    # Wifi signal strength (%)
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_WIFI_STRENGTH,
        translation_key=PTDevicesSensors.DEVICE_WIFI_STRENGTH,
        native_unit_of_measurement=PERCENTAGE,
        entity_registry_enabled_default=False,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(
            int, data.get(PTDevicesSensors.DEVICE_WIFI_STRENGTH)
        ),
    ),
    # LoRa signal strength (dBm)
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.TX_SIGNAL_STRENGTH,
        translation_key=PTDevicesSensors.TX_SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_registry_enabled_default=False,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: cast(
            float, data.get(PTDevicesSensors.TX_SIGNAL_STRENGTH)
        ),
    ),
    # Battery voltage (Volts)
    PTDevicesSensorEntityDescription(
        key=PTDevicesSensors.DEVICE_BATTERY_VOLTAGE,
        translation_key=PTDevicesSensors.DEVICE_BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: cast(
            float, data.get(PTDevicesSensors.DEVICE_BATTERY_VOLTAGE)
        ),
        suggested_display_precision=2,
    ),
)


_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_REPORTED_RE = re.compile(
    r"([A-Z][a-z]{2}) (\d{1,2})(?:st|nd|rd|th)?,?(?: (\d{4}),?)? (\d{1,2}):(\d{2}) ([AP]M)"
)


def parse_reported(value: Any, now: datetime) -> datetime | None:
    """Parse the API's report times, e.g. "Sep 30th, 11:18 PM".

    The API gives these in UTC and without a year, so the year is the one that
    puts the time latest without being more than a day after ``now``.
    """
    if not isinstance(value, str) or not (match := _REPORTED_RE.fullmatch(value.strip())):
        return None
    month, day, year, hour, minute, meridiem = match.groups()
    if month not in _MONTHS:
        return None
    hour_24 = int(hour) % 12 + (12 if meridiem == "PM" else 0)
    candidates: list[datetime] = []
    for candidate in ((int(year),) if year else (now.year + 1, now.year, now.year - 1)):
        try:
            candidates.append(
                datetime(
                    candidate, _MONTHS.index(month) + 1, int(day), hour_24, int(minute), tzinfo=UTC
                )
            )
        except ValueError:
            continue
    if year:
        return candidates[0] if candidates else None
    # Without a year, take the latest that isn't in the future (allowing for clock skew).
    past = [c for c in candidates if c <= now + timedelta(days=1)]
    return max(past) if past else None


def _number(value: Any) -> float | None:
    """Return a reading as a float, tolerating unit suffixes like "100%"."""
    if value is None:
        return None
    try:
        return float(str(value).strip(ascii_letters + "%° "))
    except ValueError:
        return None


def _imperial(device: dict[str, Any]) -> bool:
    return device.get("units") in ("US Imperial", "British Imperial")


_FEET_TO_METERS = 0.3048
_US_GALLON_TO_LITERS = 3.785411784


def _tank_depth_m(device: dict[str, Any]) -> float | None:
    """Tank depth in metres; the app takes it in feet on imperial accounts."""
    depth = _number(device.get("depth"))
    if depth is None:
        return None
    return depth * _FEET_TO_METERS if _imperial(device) else depth


def _water_depth(device: dict[str, Any]) -> float | None:
    depth = _tank_depth_m(device)
    percent = _number(device.get(PTDevicesSensors.LEVEL_PERCENT))
    if depth is None or percent is None:
        return None
    return depth * percent / 100


@dataclass(kw_only=True, frozen=True)
class PTDevicesExtraSensorEntityDescription(SensorEntityDescription):
    """A sensor the core integration doesn't offer, built from the raw API fields."""

    exists_fn: Callable[[dict[str, Any]], bool]
    value_fn: Callable[[dict[str, Any]], float | datetime | None]
    unit_fn: Callable[[dict[str, Any]], str] | None = None


EXTRA_SENSOR_DESCRIPTIONS: tuple[PTDevicesExtraSensorEntityDescription, ...] = (
    # When the tank transmitter last reported a level
    PTDevicesExtraSensorEntityDescription(
        key="tx_reported",
        translation_key="tx_reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        exists_fn=lambda d: "tx_reported" in d,
        value_fn=lambda d: parse_reported(d.get("tx_reported"), dt_util.utcnow()),
    ),
    # When the receiver last reported to the cloud
    PTDevicesExtraSensorEntityDescription(
        key="reported",
        translation_key="reported",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda d: "reported" in d,
        value_fn=lambda d: parse_reported(d.get("reported"), dt_util.utcnow()),
    ),
    PTDevicesExtraSensorEntityDescription(
        key="enclosure_temperature",
        translation_key="enclosure_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        exists_fn=lambda d: "enclosure_temperature" in d,
        value_fn=lambda d: _number(d.get("enclosure_temperature")),
        unit_fn=lambda d: (
            UnitOfTemperature.FAHRENHEIT
            if d.get("temperature_units") == "F"
            else UnitOfTemperature.CELSIUS
        ),
    ),
    # Tank depth as set up in the PTDevices app
    PTDevicesExtraSensorEntityDescription(
        key="tank_depth",
        translation_key="tank_depth",
        device_class=SensorDeviceClass.DISTANCE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfLength.METERS,
        suggested_display_precision=2,
        exists_fn=lambda d: "depth" in d,
        value_fn=_tank_depth_m,
    ),
    PTDevicesExtraSensorEntityDescription(
        key="water_depth",
        translation_key="water_depth",
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        exists_fn=lambda d: "depth" in d and PTDevicesSensors.LEVEL_PERCENT in d,
        native_unit_of_measurement=UnitOfLength.METERS,
        value_fn=_water_depth,
        suggested_display_precision=2,
    ),
)

CAPACITY_VOLUME_KEY = "capacity_volume"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: PTDevicesConfigEntry,
    async_add_entity: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up PTDevices sensors from config entries."""
    coordinator = config_entry.runtime_data
    capacities: dict[str, float] = config_entry.options.get(CONF_CAPACITIES, {})
    unit = capacity_unit(config_entry.options, coordinator.data)
    to_liters = _US_GALLON_TO_LITERS if unit == UnitOfVolume.GALLONS else 1.0

    # A cleared capacity's sensor isn't recreated; drop it from the registry too.
    ent_reg = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(ent_reg, config_entry.entry_id):
        if entity.domain == "sensor" and entity.unique_id.endswith(f"_{CAPACITY_VOLUME_KEY}"):
            device_id = entity.unique_id.removesuffix(f"_{CAPACITY_VOLUME_KEY}").split("_", 1)[-1]
            if not capacities.get(device_id):
                ent_reg.async_remove(entity.entity_id)

    known_sensors: set[tuple[str, str]] = set()

    def _check_device() -> None:
        for device_id in sorted(coordinator.data):
            device = coordinator.data[device_id]
            new_entities: list[SensorEntity] = [
                PTDevicesSensorEntity(coordinator, sensor, device_id)
                for sensor in SENSOR_DESCRIPTIONS
                if sensor.key in device and (device_id, sensor.key) not in known_sensors
            ]
            new_entities += [
                PTDevicesExtraSensorEntity(coordinator, sensor, device_id)
                for sensor in EXTRA_SENSOR_DESCRIPTIONS
                if sensor.exists_fn(device) and (device_id, sensor.key) not in known_sensors
            ]
            if (
                capacities.get(device_id)
                and PTDevicesSensors.LEVEL_PERCENT in device
                and (device_id, CAPACITY_VOLUME_KEY) not in known_sensors
            ):
                new_entities.append(
                    PTDevicesCapacityVolumeEntity(
                        coordinator, device_id, capacities[device_id] * to_liters, unit
                    )
                )
            if not new_entities:
                continue
            known_sensors.update(
                (device_id, entity.entity_description.key) for entity in new_entities
            )
            async_add_entity(new_entities)

    _check_device()
    config_entry.async_on_unload(coordinator.async_add_listener(_check_device))


class PTDevicesSensorEntity(PTDevicesEntity, SensorEntity):
    """Sensor entity for PTDevices Integration."""

    entity_description: PTDevicesSensorEntityDescription

    def __init__(
        self,
        coordinator: PTDevicesCoordinator,
        description: PTDevicesSensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(
            coordinator,
            description.key,
            device_id,
        )

        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | int | str | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)


class PTDevicesExtraSensorEntity(PTDevicesEntity, SensorEntity):
    """A sensor built from the raw API fields."""

    entity_description: PTDevicesExtraSensorEntityDescription

    def __init__(
        self,
        coordinator: PTDevicesCoordinator,
        description: PTDevicesExtraSensorEntityDescription,
        device_id: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator, description.key, device_id)
        self.entity_description = description

    @property
    @override
    def native_value(self) -> float | datetime | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.device)

    @property
    @override
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, which can depend on the account's settings."""
        if self.entity_description.unit_fn is not None:
            return self.entity_description.unit_fn(self.device)
        return super().native_unit_of_measurement


class PTDevicesCapacityVolumeEntity(PTDevicesEntity, SensorEntity):
    """Volume from the level and the tank capacity set in the options."""

    _attr_native_unit_of_measurement = UnitOfVolume.LITERS

    def __init__(
        self,
        coordinator: PTDevicesCoordinator,
        device_id: str,
        capacity_liters: float,
        display_unit: str,
    ) -> None:
        """Initialize sensor."""
        self.entity_description = SensorEntityDescription(
            key=CAPACITY_VOLUME_KEY,
            translation_key=CAPACITY_VOLUME_KEY,
            device_class=SensorDeviceClass.VOLUME_STORAGE,
            state_class=SensorStateClass.MEASUREMENT,
            suggested_display_precision=0,
            suggested_unit_of_measurement=display_unit,
        )
        super().__init__(coordinator, CAPACITY_VOLUME_KEY, device_id)
        self._capacity = capacity_liters

    @property
    @override
    def native_value(self) -> float | None:
        """Return the volume in litres."""
        percent = _number(self.device.get(PTDevicesSensors.LEVEL_PERCENT))
        return None if percent is None else round(self._capacity * percent / 100, 3)
