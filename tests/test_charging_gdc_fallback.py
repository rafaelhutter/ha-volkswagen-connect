"""Self-check: charging/status falls back to wcar where mbb refuses it (#45).

    python3 tests/test_charging_gdc_fallback.py
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path

# Load the module by path: importing the package would pull in homeassistant.
_SRC = Path(__file__).resolve().parents[1] / "custom_components/volkswagen_connect/website_portal.py"
_spec = importlib.util.spec_from_file_location("website_portal", _SRC)
wp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wp)

VIN = "WVWZZZ3CZLE000001"
CHARGING = json.dumps({"data": {"batteryStatus": {"currentSOC_pct": 57, "cruisingRangeElectric_km": 41}}})


def _portal(own_gdc: str, serving: set[str]) -> tuple[wp.WebsitePortalClient, list[str]]:
    """A client routed to ``own_gdc`` whose charging/status only ``serving`` clusters answer."""
    portal = wp.WebsitePortalClient(None, email="a@b.c", password="x")
    asked: list[str] = []

    async def gdc_for(vin: str) -> str:
        return own_gdc

    async def get(path: str, accept: str = "") -> tuple[int, str]:
        gdc = path.split("gdc=myvw-", 1)[1].split("-prod", 1)[0]
        asked.append(gdc)
        if gdc not in serving:
            raise wp.WebsitePortalVehicleError(f"refused on {gdc}")
        return 200, CHARGING

    portal._gdc_for, portal._get = gdc_for, get
    return portal, asked


async def _poll(portal: wp.WebsitePortalClient) -> dict | None:
    try:
        return await portal.get_charging(VIN)
    except wp.WebsitePortalVehicleError:
        return None


async def main() -> None:
    # The #45 Passat GTE: mbb refuses, wcar serves; later polls go straight to wcar.
    portal, asked = _portal("mbb", {"wcar"})
    assert (await _poll(portal))["soc"] == 57
    assert (await _poll(portal))["electric_range"] == 41
    assert asked == ["mbb", "wcar", "wcar"], asked

    # A combustion MBB car neither cluster serves: wcar is tried once, never again.
    portal, asked = _portal("mbb", set())
    assert await _poll(portal) is None
    assert await _poll(portal) is None
    assert asked == ["mbb", "wcar", "mbb"], asked

    # A car already on wcar has nothing to fall back to.
    portal, asked = _portal("wcar", set())
    assert await _poll(portal) is None
    assert asked == ["wcar"], asked

    # A car its own cluster serves never touches wcar.
    portal, asked = _portal("mbb", {"mbb"})
    assert (await _poll(portal))["soc"] == 57
    assert asked == ["mbb"], asked
    print("ok")


if __name__ == "__main__":
    asyncio.run(main())
