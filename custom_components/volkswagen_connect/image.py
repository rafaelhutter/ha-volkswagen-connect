"""Image platform: the vehicle's exterior photo.

The authproxy resolves a VIN to a set of public VILMA CDN URLs; we expose the
side view as a Home Assistant image entity (served by URL — the CDN assets need
no authentication).
"""

from __future__ import annotations

from homeassistant.components.image import ImageEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import VolkswagenConnectConfigEntry, VolkswagenConnectCoordinator, VehicleData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VolkswagenConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def _add_new() -> None:
        new: list[ImageEntity] = []
        for vin, vehicle in (coordinator.data or {}).items():
            if vin in known or not vehicle.image_url:
                continue
            known.add(vin)
            new.append(VolkswagenConnectVehicleImage(hass, coordinator, vin))
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


class VolkswagenConnectVehicleImage(CoordinatorEntity[VolkswagenConnectCoordinator], ImageEntity):
    """Exterior side-view photo of the vehicle."""

    _attr_has_entity_name = True
    _attr_name = "Image"
    _attr_content_type = "image/png"

    def __init__(
        self, hass: HomeAssistant, coordinator: VolkswagenConnectCoordinator, vin: str
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._vin = vin
        self._attr_unique_id = f"{vin}_image"
        self._current_url: str | None = None
        v = self._vehicle
        if v and v.image_url:
            self._current_url = v.image_url
            self._attr_image_url = v.image_url
            self._attr_image_last_updated = dt_util.utcnow()

    @property
    def _vehicle(self) -> VehicleData | None:
        return (self.coordinator.data or {}).get(self._vin)

    @property
    def device_info(self) -> DeviceInfo | None:
        v = self._vehicle
        return _device(v) if v else None

    @callback
    def _handle_coordinator_update(self) -> None:
        v = self._vehicle
        url = v.image_url if v else None
        if url and url != self._current_url:
            self._current_url = url
            self._attr_image_url = url
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()
