"""The Volkswagen Connect integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import VolkswagenConnectConfigEntry, VolkswagenConnectCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.IMAGE]


async def async_setup_entry(hass: HomeAssistant, entry: VolkswagenConnectConfigEntry) -> bool:
    """Set up Volkswagen Connect from a config entry."""
    coordinator = VolkswagenConnectCoordinator(hass, entry)
    # Roll the website-portal session up front so the very first poll runs on a
    # fresh session (the restored cookies may be stale after a long downtime).
    await coordinator.async_refresh_session(force=True)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: VolkswagenConnectConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
