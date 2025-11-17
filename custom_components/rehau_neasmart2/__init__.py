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
    
    # Create hub instance with new configuration structure
    climate_system = hub.RehauNeasmart2ClimateControlSystem(
        hass,
        entry.data
    )
    
    # Initialize HTTP client and test connection with proper cleanup
    try:
        await climate_system.async_init()
        if not await climate_system.test_connection():
            await climate_system.async_close()
            raise ConfigEntryNotReady("Unable to connect to Neasmart gateway")
    except ConfigEntryNotReady:
        # Re-raise ConfigEntryNotReady without wrapping
        raise
    except (ConnectionError, Exception) as err:
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


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:
        # Already at version 1, check if old format needs migration
        data = dict(entry.data)
        
        # Check if it's old format (has neasmart_gw_server_host)
        if "neasmart_gw_server_host" in data:
            # Migrate from old format to new format
            old_zones = data.get("zones", "").split(",")
            zones = []
            for i, zone_name in enumerate(old_zones):
                if zone_name.strip():
                    base_id = (i // 12) + 1
                    zone_id = (i % 12) + 1
                    zones.append({
                        "base_id": base_id,
                        "zone_id": zone_id,
                        "label": zone_name.strip()
                    })
            
            new_data = {
                "climate_system_name": data.get("climate_system_name", "Rehau Neasmart 2.0"),
                "api_url": data.get("neasmart_gw_server_host", ""),
                "api_port": data.get("neasmart_gw_server_port", 80),
                "zones": zones
            }
            
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info("Migration to new format successful")

    return True
