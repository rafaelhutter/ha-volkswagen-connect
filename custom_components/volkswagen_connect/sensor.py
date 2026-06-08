"""Sensor platform for the Volkswagen Connect integration.

The EU Data Act payload schema varies by enabled data clusters and is not known
ahead of time, so value sensors are created dynamically from the flattened
dataset keys (and new keys are added as they first appear). Each vehicle also
gets a stable "status" sensor that always exists, even before any content is
delivered.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import VolkswagenConnectConfigEntry, VolkswagenConnectCoordinator, VehicleData

# Friendly metadata for known (authproxy-derived) keys. Unknown keys still get
# a generic sensor.
KNOWN_KEYS: dict[str, dict[str, Any]] = {
    "odometer": {
        "name": "Odometer",
        "device_class": SensorDeviceClass.DISTANCE,
        "unit": UnitOfLength.KILOMETERS,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:counter",
    },
    "inspection_due_days": {"name": "Inspection due", "unit": UnitOfTime.DAYS, "icon": "mdi:wrench-clock"},
    "inspection_due_km": {"name": "Inspection due", "device_class": SensorDeviceClass.DISTANCE, "unit": UnitOfLength.KILOMETERS},
    "oil_service_due_days": {"name": "Oil service due", "unit": UnitOfTime.DAYS, "icon": "mdi:oil"},
    "oil_service_due_km": {"name": "Oil service due", "device_class": SensorDeviceClass.DISTANCE, "unit": UnitOfLength.KILOMETERS},
    "last_report": {"name": "Last vehicle report", "device_class": SensorDeviceClass.TIMESTAMP, "icon": "mdi:clock-check"},
    # Vehicle health + lock history (from the authproxy)
    "warning_lights": {"name": "Warning lights", "state_class": SensorStateClass.MEASUREMENT, "icon": "mdi:car-light-alert"},
    "last_lock_action": {"name": "Last lock command", "icon": "mdi:car-key"},
    "last_lock_action_time": {"name": "Last lock command time", "device_class": SensorDeviceClass.TIMESTAMP, "icon": "mdi:clock-outline"},
    # Live battery / charging (from charging/status)
    "soc": {"name": "Battery", "device_class": SensorDeviceClass.BATTERY, "unit": PERCENTAGE, "state_class": SensorStateClass.MEASUREMENT},
    "electric_range": {"name": "Electric range", "device_class": SensorDeviceClass.DISTANCE, "unit": UnitOfLength.KILOMETERS, "icon": "mdi:map-marker-distance"},
    "target_soc": {"name": "Target battery", "unit": PERCENTAGE, "icon": "mdi:battery-charging-high"},
    "battery_temp": {"name": "Battery temperature", "device_class": SensorDeviceClass.TEMPERATURE, "unit": UnitOfTemperature.CELSIUS, "state_class": SensorStateClass.MEASUREMENT},
    "charging_state": {"name": "Charging state", "icon": "mdi:ev-station"},
    "charge_power": {"name": "Charge power", "device_class": SensorDeviceClass.POWER, "unit": UnitOfPower.KILO_WATT, "state_class": SensorStateClass.MEASUREMENT},
    "charge_rate": {"name": "Charge rate", "unit": UnitOfSpeed.KILOMETERS_PER_HOUR, "icon": "mdi:speedometer"},
    "charge_time_remaining": {"name": "Charge time remaining", "device_class": SensorDeviceClass.DURATION, "unit": UnitOfTime.MINUTES, "icon": "mdi:timer-sand"},
    "charge_mode": {"name": "Charge mode", "icon": "mdi:cog"},
    "plug_connection": {"name": "Plug", "icon": "mdi:power-plug"},
    "plug_lock": {"name": "Plug lock", "icon": "mdi:lock"},
    "external_power": {"name": "External power", "icon": "mdi:transmission-tower"},
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolkswagenConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def _add_new() -> None:
        new: list[SensorEntity] = []
        for vin, vehicle in (coordinator.data or {}).items():
            status_key = (vin, "__status__")
            if status_key not in known:
                known.add(status_key)
                new.append(VolkswagenConnectStatusSensor(coordinator, vin))
            for key in vehicle.values:
                vk = (vin, key)
                if vk not in known:
                    known.add(vk)
                    new.append(VolkswagenConnectValueSensor(coordinator, vin, key))
        if new:
            async_add_entities(new)

    _add_new()
    entry.async_on_unload(coordinator.async_add_listener(_add_new))


def _device(vehicle: VehicleData) -> DeviceInfo:
    name = vehicle.info.get("nickName") or vehicle.info.get("licensePlate") or vehicle.vin
    return DeviceInfo(
        identifiers={(DOMAIN, vehicle.vin)},
        manufacturer="Volkswagen",
        name=name,
        model=vehicle.info.get("nickName"),
        serial_number=vehicle.vin,
    )


class _Base(CoordinatorEntity[VolkswagenConnectCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: VolkswagenConnectCoordinator, vin: str) -> None:
        super().__init__(coordinator)
        self._vin = vin

    @property
    def _vehicle(self) -> VehicleData | None:
        return (self.coordinator.data or {}).get(self._vin)

    @property
    def device_info(self) -> DeviceInfo | None:
        v = self._vehicle
        return _device(v) if v else None


class VolkswagenConnectStatusSensor(_Base):
    """Always-present per-vehicle status (ok / no_data / not_configured)."""

    _attr_icon = "mdi:database-sync"
    _attr_translation_key = "data_status"

    def __init__(self, coordinator: VolkswagenConnectCoordinator, vin: str) -> None:
        super().__init__(coordinator, vin)
        self._attr_unique_id = f"{vin}_data_status"

    @property
    def native_value(self) -> StateType:
        v = self._vehicle
        return v.status if v else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        v = self._vehicle
        if not v:
            return {}
        return {
            "vin": v.vin,
            "nickname": v.info.get("nickName"),
            "license_plate": v.info.get("licensePlate"),
            "enrollment_status": v.info.get("enrollmentStatus"),
            "data_request_id": v.identifier,
            "latest_dataset": v.dataset,
            "created_on": v.created_on,
        }


class VolkswagenConnectValueSensor(_Base):
    """A single flattened value from the latest delivered dataset."""

    def __init__(self, coordinator: VolkswagenConnectCoordinator, vin: str, key: str) -> None:
        super().__init__(coordinator, vin)
        self._key = key
        self._attr_unique_id = f"{vin}_{key}"
        meta = KNOWN_KEYS.get(key, {})
        self._attr_name = meta.get("name", key)
        if "device_class" in meta:
            self._attr_device_class = meta["device_class"]
        if "unit" in meta:
            self._attr_native_unit_of_measurement = meta["unit"]
        if "state_class" in meta:
            self._attr_state_class = meta["state_class"]
        if "icon" in meta:
            self._attr_icon = meta["icon"]

    @property
    def native_value(self) -> StateType:
        v = self._vehicle
        if not v:
            return None
        val = v.values.get(self._key)
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP and isinstance(val, str):
            return dt_util.parse_datetime(val)
        if isinstance(val, bool):
            return str(val).lower()
        return val

    @property
    def available(self) -> bool:
        return super().available and self._vehicle is not None
