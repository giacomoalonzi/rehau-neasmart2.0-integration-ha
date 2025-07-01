"""The Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from . import hub
from .const import DOMAIN
from .exceptions import ConnectionError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.CLIMATE, Platform.SELECT]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Rehau Neasmart 2.0 from a config entry."""
    
    # Create hub instance
    climate_system = hub.RehauNeasmart2ClimateControlSystem(
        hass,
        entry.data["climate_system_name"],
        entry.data["neasmart_gw_server_host"],
        entry.data["neasmart_gw_server_port"],
        entry.data["zones"],
        entry.data.get("mixed_groups", 0),
        entry.data.get("pumps_regs_mapping", ""),
        entry.data.get("dehumidificators_regs_mapping", "")
    )
    
    # Initialize HTTP client
    await climate_system.async_init()
    
    # Test connection
    try:
        if not await climate_system.test_connection():
            raise ConfigEntryNotReady("Unable to connect to Neasmart gateway")
    except ConnectionError as err:
        _LOGGER.error("Failed to connect to Neasmart gateway: %s", err)
        await climate_system.async_close()
        raise ConfigEntryNotReady from err
    
    # Store hub instance
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = climate_system
    
    # Forward entry setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register update listener
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Get hub instance
        climate_system = hass.data[DOMAIN][entry.entry_id]
        
        # Close HTTP connections
        await climate_system.async_close()
        
        # Remove from data
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
