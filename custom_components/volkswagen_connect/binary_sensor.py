"""Binary sensor platform: boolean vehicle flags with proper device classes.

The EU Data Act feed sends a few vehicle-level booleans (lock/open status) that
read far clearer as binary sensors (Locked/Unlocked, Open/Closed) than as raw
true/false text. These keys are handled here and skipped by the sensor platform.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import VolkswagenConnectConfigEntry, VolkswagenConnectCoordinator, VehicleData

# Boolean keys exposed as binary sensors with a device class. ``invert`` maps our
# value to HA's on/off convention (the lock device class reads on = unlocked).
BINARY_KEYS: dict[str, dict[str, Any]] = {
    "locked": {"name": "Lock", "device_class": BinarySensorDeviceClass.LOCK, "invert": True},
    "open": {"name": "Open", "device_class": BinarySensorDeviceClass.OPENING},
    "trunk.locked": {"name": "Trunk lock", "device_class": BinarySensorDeviceClass.LOCK, "invert": True},
    "trunk.open": {"name": "Trunk", "device_class": BinarySensorDeviceClass.OPENING},
}

_TRUE = {"true", "1", "on", "yes"}
_FALSE = {"false", "0", "off", "no"}


def _as_bool(value: Any) -> bool | None:
    """Coerce VW's true/false (string or bool) to a real bool, else None."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s in _TRUE:
            return True
        if s in _FALSE:
            return False
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolkswagenConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[tuple[str, str]] = set()

    @callback
    def _add_new() -> None:
        new: list[BinarySensorEntity] = []
        for vin, vehicle in (coordinator.data or {}).items():
            for key in BINARY_KEYS:
                if key in vehicle.values and (vin, key) not in known:
                    known.add((vin, key))
                    new.append(VolkswagenConnectBinarySensor(coordinator, vin, key))
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


class VolkswagenConnectBinarySensor(
    CoordinatorEntity[VolkswagenConnectCoordinator], BinarySensorEntity
):
    """A boolean vehicle flag (lock / open) rendered with a device class."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: VolkswagenConnectCoordinator, vin: str, key: str
    ) -> None:
        super().__init__(coordinator)
        self._vin = vin
        self._key = key
        meta = BINARY_KEYS[key]
        self._invert = meta.get("invert", False)
        self._attr_unique_id = f"{vin}_{key}"
        self._attr_name = meta["name"]
        self._attr_device_class = meta["device_class"]

    @property
    def _vehicle(self) -> VehicleData | None:
        return (self.coordinator.data or {}).get(self._vin)

    @property
    def device_info(self) -> DeviceInfo | None:
        v = self._vehicle
        return _device(v) if v else None

    @property
    def is_on(self) -> bool | None:
        v = self._vehicle
        b = _as_bool(v.values.get(self._key)) if v else None
        if b is None:
            return None
        return (not b) if self._invert else b

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        v = self._vehicle
        raw = v.values.get(self._key) if v else None
        return {"raw_value": raw} if raw is not None else None

    @property
    def available(self) -> bool:
        v = self._vehicle
        return super().available and v is not None and _as_bool(v.values.get(self._key)) is not None
