"""Self-check: one refused portal endpoint must not blank the others (#30).

Needs the integration's deps, so run it inside the HA container:
    python3 tests/test_portal_merge.py
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

# coordinator.py uses relative imports, so it has to load as part of the package.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from custom_components.volkswagen_connect import coordinator as co  # noqa: E402
from custom_components.volkswagen_connect.website_portal import (  # noqa: E402
    WebsitePortalAuthError,
    WebsitePortalVehicleError,
)
from homeassistant.exceptions import ConfigEntryAuthFailed  # noqa: E402

VIN = "WVWZZZ00000000001"


class FakePortal:
    """Portal whose named endpoints raise WebsitePortalVehicleError."""

    def __init__(self, *refused: str) -> None:
        self.refused = set(refused)

    def _answer(self, what: str, payload: dict) -> dict:
        if what in self.refused:
            raise WebsitePortalVehicleError(f"portal refused {what} (HTTP 412)")
        return payload

    async def get_maintenance(self, vin: str) -> dict:
        return self._answer("maintenance", {"mileage_km": 42000})

    async def get_charging(self, vin: str) -> dict:
        return self._answer("charging", {"soc": 80})

    async def get_warning_lights(self, vin: str) -> dict:
        return self._answer("warning_lights", {"warning_lights": 0})

    async def get_lock_history(self, vin: str) -> dict:
        return self._answer("lock_history", {"last_lock_action": "locked"})

    async def get_vehicle_images(self, vin: str) -> dict:
        return self._answer("images", {"side_left": "https://example.invalid/a.png"})

    async def get_vehicle_info(self, vin: str) -> dict:
        return self._answer("info", {"modelName": "ID. Buzz"})


class FakeCoordinator:
    """Just enough coordinator to drive _merge_one unbound."""

    def __init__(self, portal: FakePortal) -> None:
        self.portal = portal
        self.portal_keys = co.defaultdict(set)

    _portal_fetch = co.VolkswagenConnectCoordinator._portal_fetch
    _merge_one = co.VolkswagenConnectCoordinator._merge_one
    _merge_portal = co.VolkswagenConnectCoordinator._merge_portal

    async def async_refresh_session(self) -> None:
        pass

    def _persist_portal_cookies(self) -> None:
        pass


class DeadSessionPortal(FakePortal):
    async def get_maintenance(self, vin: str) -> dict:
        raise WebsitePortalAuthError("portal session rejected (HTTP 401)")


def _merge(*refused: str) -> co.VehicleData:
    data = co.VehicleData(vin=VIN, info={"vin": VIN})
    asyncio.run(FakeCoordinator(FakePortal(*refused))._merge_one(VIN, data))
    return data


def test_healthy_vehicle_gets_every_signal() -> None:
    data = _merge()
    assert data.values["odometer"] == 42000, data.values
    assert data.values["soc"] == 80, data.values
    assert data.image_url, data.image_urls
    assert data.info["modelName"] == "ID. Buzz", data.info
    assert data.portal_ok


def test_refused_maintenance_keeps_the_rest() -> None:
    """The #30 shape: a refused first endpoint used to abort the whole vehicle."""
    data = _merge("maintenance")
    assert "odometer" not in data.values, data.values
    assert data.values["soc"] == 80, data.values
    assert data.values["last_lock_action"] == "locked", data.values
    assert data.image_url, data.image_urls


def test_combustion_car_still_gets_odometer() -> None:
    data = _merge("charging")
    assert data.values["odometer"] == 42000, data.values
    assert "soc" not in data.values, data.values


def test_portal_serving_nothing_is_not_reported_ok() -> None:
    """portal_ok gates the duplicate purge; a blank merge must not claim data."""
    data = _merge("maintenance", "charging", "warning_lights", "lock_history", "images", "info")
    assert data.values == {}, data.values
    assert not data.portal_ok


def test_dead_session_reaches_reauth() -> None:
    """Swallowing it per vehicle kept polling alive, mailing an OTP each cycle (#31)."""
    result = {VIN: co.VehicleData(vin=VIN, info={"vin": VIN})}
    try:
        asyncio.run(FakeCoordinator(DeadSessionPortal())._merge_portal(result))
    except ConfigEntryAuthFailed:
        return
    raise AssertionError("dead portal session was swallowed")


class FakeEuClient:
    """An EU Data Act feed that always carries the portal's SoC as a duplicate."""

    async def list_vehicles(self) -> list[dict]:
        return [{"vin": VIN}]

    async def get_metadata(self, vin: str) -> dict:
        return {"Identifier": "request"}

    async def get_latest(self, vin: str, identifier: str) -> dict:
        return {"dataset": "d.zip", "created_on": None, "captured_at": None,
                "values": {"battery_state_report.soc": 79}}


class OutagePortal(FakePortal):
    """A portal that can time out as a whole, as on homi 2026-10-16."""

    down = False

    async def get_maintenance(self, vin: str) -> dict:
        if self.down:
            raise TimeoutError("ReadTimeout")
        return await super().get_maintenance(vin)


class PollingCoordinator(FakeCoordinator):
    _async_update_data = co.VolkswagenConnectCoordinator._async_update_data

    def __init__(self, portal: FakePortal) -> None:
        super().__init__(portal)
        self.client, self.data = FakeEuClient(), None
        self.euda_values, self.drivetrain = co.defaultdict(dict), co.defaultdict(set)


def test_portal_outage_does_not_let_a_duplicate_back_in() -> None:
    """A portal-only timeout let the EU copies in, spawning sensors that then sat dead (#18)."""
    portal = OutagePortal()
    coordinator = PollingCoordinator(portal)
    assert "battery_state_report.soc" not in asyncio.run(coordinator._async_update_data())[VIN].values
    portal.down = True
    values = asyncio.run(coordinator._async_update_data())[VIN].values
    assert "battery_state_report.soc" not in values, values


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
    print("\nall checks passed")
