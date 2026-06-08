"""DataUpdateCoordinator for the Volkswagen EU Data Act integration.

Two data sources, merged per vehicle:
  * EU Data Act portal  — 15-min "continuous data" (when the car reports).
  * volkswagen.de authproxy (optional) — reliable odometer / service / info.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_BRAND,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_WEBSITE_COOKIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    STATUS_NO_DATA,
    STATUS_NOT_CONFIGURED,
    STATUS_OK,
)
from .eu_data_act import (
    DEFAULT_BRAND,
    EuDataActAuthError,
    EuDataActClient,
    EuDataActError,
    EuDataActNotConfigured,
)
from .website_portal import WebsitePortalAuthError, WebsitePortalClient

_LOGGER = logging.getLogger(__name__)


@dataclass
class VehicleData:
    """Per-vehicle snapshot exposed to entities."""

    vin: str
    info: dict[str, Any]
    status: str = STATUS_NO_DATA
    identifier: str | None = None
    dataset: str | None = None
    created_on: str | None = None
    values: dict[str, Any] = field(default_factory=dict)
    portal_ok: bool = False


type EuDataActConfigEntry = ConfigEntry["EuDataActCoordinator"]

# maintenance/status field -> clean sensor key
_MAINTENANCE_MAP = {
    "mileage_km": "odometer",
    "inspectionDue_days": "inspection_due_days",
    "inspectionDue_km": "inspection_due_km",
    "oilServiceDue_days": "oil_service_due_days",
    "oilServiceDue_km": "oil_service_due_km",
    "carCapturedTimestamp": "last_report",
}


class EuDataActCoordinator(DataUpdateCoordinator[dict[str, VehicleData]]):
    """Polls the EU Data Act portal (and optionally the website authproxy)."""

    def __init__(self, hass: HomeAssistant, entry: EuDataActConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL)
        self.entry = entry
        self.client = EuDataActClient(
            async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar()),
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            brand=entry.data.get(CONF_BRAND, DEFAULT_BRAND),
        )
        # Website portal is optional: only active if we have a persisted session.
        self.portal: WebsitePortalClient | None = None
        cookies = entry.data.get(CONF_WEBSITE_COOKIES)
        if cookies:
            self.portal = WebsitePortalClient(
                async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar()),
                email=entry.data[CONF_EMAIL],
                password=entry.data[CONF_PASSWORD],
            )
            self.portal.import_cookies(cookies)

    async def _async_update_data(self) -> dict[str, VehicleData]:
        try:
            vehicles = await self.client.list_vehicles()
        except EuDataActAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except EuDataActError as err:
            raise UpdateFailed(str(err)) from err

        result: dict[str, VehicleData] = {}
        for v in vehicles:
            vin = v.get("vin")
            if not vin:
                continue
            data = VehicleData(vin=vin, info=dict(v))
            try:
                meta = await self.client.get_metadata(vin)
                data.identifier = meta.get("Identifier")
                latest = await self.client.get_latest(vin, data.identifier)
                if latest is None:
                    data.status = STATUS_NO_DATA
                else:
                    data.status = STATUS_OK
                    data.dataset = latest["dataset"]
                    data.created_on = latest["created_on"]
                    data.values = dict(latest["values"])
            except EuDataActNotConfigured:
                data.status = STATUS_NOT_CONFIGURED
            except EuDataActAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except EuDataActError as err:
                _LOGGER.warning("EU Data Act: %s update failed: %s", vin, err)
            result[vin] = data

        if self.portal is not None:
            await self._merge_portal(result)
        return result

    async def _merge_portal(self, result: dict[str, VehicleData]) -> None:
        """Best-effort: enrich vehicles with portal data. Never blocks setup.

        Uses the persisted session directly; the client re-authenticates on
        demand (only if a request shows the session has expired).
        """
        assert self.portal is not None
        try:
            # If EU Data Act surfaced no vehicles, discover the VIN via the portal.
            if not result:
                vin = await self.portal.get_first_vin()
                if vin:
                    result[vin] = VehicleData(vin=vin, info={"vin": vin})
            for vin, data in result.items():
                maint = await self.portal.get_maintenance(vin)
                for raw, clean in _MAINTENANCE_MAP.items():
                    if maint.get(raw) is not None:
                        data.values[clean] = maint[raw]
                info = await self.portal.get_vehicle_info(vin)
                for k in ("nickName", "nickname", "licensePlate", "modelName", "engine", "exteriorColor"):
                    if info.get(k) and not data.info.get(k):
                        data.info[k] = info[k]
                data.portal_ok = True
            # Persist the (possibly refreshed) cookies for the next restart.
            self.hass.config_entries.async_update_entry(
                self.entry,
                data={**self.entry.data, CONF_WEBSITE_COOKIES: self.portal.export_cookies()},
            )
        except WebsitePortalAuthError as err:
            _LOGGER.warning(
                "Website portal session expired (%s). Odometer/service data is paused; "
                "open the integration and Reconfigure to restore it.",
                err,
            )
        except Exception as err:  # noqa: BLE001 - portal must never break EU Data Act
            _LOGGER.warning("Website portal update failed, skipping this cycle: %s", err)
