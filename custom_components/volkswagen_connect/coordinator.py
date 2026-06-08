"""DataUpdateCoordinator for the Volkswagen Connect integration.

Two data sources, merged per vehicle:
  * volkswagen.de authproxy — the reliable source (battery/charging, odometer,
    service, warning lights, lock history, image).
  * EU Data Act portal (optional, flaky) — 15-min "continuous data".
"""

from __future__ import annotations

import logging
import time
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

# Don't roll the session more often than this (avoids a double refresh when the
# explicit startup refresh is immediately followed by the first poll).
_MIN_REFRESH_INTERVAL_S = 600


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
    image_url: str | None = None
    portal_ok: bool = False


type VolkswagenConnectConfigEntry = ConfigEntry["VolkswagenConnectCoordinator"]

# maintenance/status field -> clean sensor key
_MAINTENANCE_MAP = {
    "mileage_km": "odometer",
    "inspectionDue_days": "inspection_due_days",
    "inspectionDue_km": "inspection_due_km",
    "oilServiceDue_days": "oil_service_due_days",
    "oilServiceDue_km": "oil_service_due_km",
    "carCapturedTimestamp": "last_report",
}


class VolkswagenConnectCoordinator(DataUpdateCoordinator[dict[str, VehicleData]]):
    """Polls the website authproxy (and optionally the EU Data Act portal)."""

    def __init__(self, hass: HomeAssistant, entry: VolkswagenConnectConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=DEFAULT_SCAN_INTERVAL)
        self.entry = entry
        # Monotonic timestamp of the last portal session refresh (None = never).
        self._last_refresh: float | None = None
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

    def _persist_portal_cookies(self) -> None:
        """Save the current portal cookies so the session survives a restart."""
        assert self.portal is not None
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={**self.entry.data, CONF_WEBSITE_COOKIES: self.portal.export_cookies()},
        )

    async def async_refresh_session(self, *, force: bool = False) -> None:
        """Roll the website-portal session (best-effort) and persist it.

        Called once at startup and again at the start of every poll, so both the
        portal's downstream tokens and the identity SSO behind the silent refresh
        stay rolled. Skips if a refresh happened within the last few minutes
        (unless ``force``), to avoid a double refresh when the startup call is
        immediately followed by the first poll. Never raises.
        """
        if self.portal is None:
            return
        if (
            not force
            and self._last_refresh is not None
            and time.monotonic() - self._last_refresh < _MIN_REFRESH_INTERVAL_S
        ):
            return
        try:
            await self.portal.refresh()
            self._last_refresh = time.monotonic()
            self._persist_portal_cookies()
        except WebsitePortalAuthError:
            _LOGGER.debug("Session refresh: SSO not usable yet; trying existing session")
        except Exception as err:  # noqa: BLE001 - never block on a refresh hiccup
            _LOGGER.debug("Session refresh failed (continuing): %s", err)

    async def _merge_portal(self, result: dict[str, VehicleData]) -> None:
        """Best-effort: enrich vehicles with portal data. Never blocks setup.

        Keep-alive: the portal session's downstream tokens expire ~30 min after
        the last login and are NOT renewed by data calls, while the identity SSO
        behind the silent refresh lapses if it isn't exercised often enough. So
        we proactively roll the session every cycle (15 min, well inside that
        window) instead of only reacting to a 401 — by which point the SSO has
        often already gone, forcing a needless re-login. Best-effort: if the
        refresh fails we still try the existing session, and only a failing
        *data* call is treated as a real auth loss.
        """
        assert self.portal is not None
        await self.async_refresh_session()

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
                # Live battery/charging telemetry (already clean keys).
                data.values.update(await self.portal.get_charging(vin))
                # Vehicle-health warning lights + last lock/unlock command.
                data.values.update(await self.portal.get_warning_lights(vin))
                data.values.update(await self.portal.get_lock_history(vin))
                # Exterior image (public CDN URL, served by the image platform).
                data.image_url = await self.portal.get_vehicle_image_url(vin)
                info = await self.portal.get_vehicle_info(vin)
                for k in ("nickName", "nickname", "licensePlate", "modelName", "engine", "exteriorColor"):
                    if info.get(k) and not data.info.get(k):
                        data.info[k] = info[k]
                data.portal_ok = True
        except WebsitePortalAuthError as err:
            _LOGGER.warning(
                "Website portal session expired (%s). Live data is paused; "
                "open the integration and Reconfigure to restore it.",
                err,
            )
        except Exception as err:  # noqa: BLE001 - portal must never break EU Data Act
            _LOGGER.warning("Website portal update failed, skipping this cycle: %s", err)
        finally:
            # Always persist the freshest cookies — the rolled SSO must survive a
            # restart even if this cycle's data calls happened to fail.
            try:
                self._persist_portal_cookies()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Could not persist portal cookies: %s", err)
