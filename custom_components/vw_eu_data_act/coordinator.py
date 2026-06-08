"""DataUpdateCoordinator for the Volkswagen EU Data Act integration."""

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


type EuDataActConfigEntry = ConfigEntry["EuDataActCoordinator"]


class EuDataActCoordinator(DataUpdateCoordinator[dict[str, VehicleData]]):
    """Polls the EU Data Act portal every 15 minutes."""

    def __init__(self, hass: HomeAssistant, entry: EuDataActConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.entry = entry
        # Dedicated session with its OWN cookie jar (don't share the portal
        # session cookies with other integrations).
        session = async_create_clientsession(hass, cookie_jar=aiohttp.CookieJar())
        self.client = EuDataActClient(
            session,
            email=entry.data[CONF_EMAIL],
            password=entry.data[CONF_PASSWORD],
            brand=entry.data.get(CONF_BRAND, DEFAULT_BRAND),
        )

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
            data = VehicleData(vin=vin, info=v)
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
                    data.values = latest["values"]
            except EuDataActNotConfigured:
                data.status = STATUS_NOT_CONFIGURED
            except EuDataActAuthError as err:
                raise ConfigEntryAuthFailed(str(err)) from err
            except EuDataActError as err:
                _LOGGER.warning("EU Data Act: %s update failed: %s", vin, err)
            result[vin] = data
        return result
