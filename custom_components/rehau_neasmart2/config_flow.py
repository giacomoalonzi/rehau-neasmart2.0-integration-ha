"""Config flow for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN
from .exceptions import ConnectionError, ConfigurationError
from .http_client import HttpClient, RehauNeasmart2ApiClient
from .models import ConfigData

_LOGGER = logging.getLogger(__name__)


# Schema for step 1: API connection
STEP_API_SCHEMA = vol.Schema(
    {
        vol.Required("api_endpoint"): str,
    }
)

# Schema for step 2: System name
STEP_SYSTEM_SCHEMA = vol.Schema(
    {
        vol.Required("climate_system_name"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rehau Neasmart 2.0."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        self._api_url: str = ""
        self._api_port: int = 80
        self._climate_system_name: str = ""
        self._zones: List[Dict[str, Any]] = []
        self._http_client: Optional[HttpClient] = None
        self._api_client: Optional[RehauNeasmart2ApiClient] = None

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - API connection."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            endpoint = user_input["api_endpoint"]
            
            try:
                if "://" not in endpoint:
                    endpoint = f"http://{endpoint}"
                
                parsed_url = urlparse(endpoint)
                
                api_url = parsed_url.hostname
                api_port = parsed_url.port
                
                if not api_url:
                    raise ValueError("Invalid endpoint")
                
                if not api_port:
                    if parsed_url.scheme == "https":
                        api_port = 443
                    else:
                        api_port = 80
                
                self._api_url = api_url
                self._api_port = api_port

                # Test API connection
                self._http_client = HttpClient(self._api_url, self._api_port)
                self._api_client = RehauNeasmart2ApiClient(self._http_client)
                
                # Test connection
                await self._api_client.health_check()
                
                # If successful, move to next step
                return await self.async_step_system_name()

            except ValueError:
                errors["base"] = "invalid_endpoint"
            except ConnectionError:
                errors["base"] = "cannot_connect"
                if self._http_client:
                    await self._http_client.close()
                    self._http_client = None
                    self._api_client = None
            except Exception as err:
                _LOGGER.exception("Unexpected exception during connection test")
                errors["base"] = "unknown"
                if self._http_client:
                    await self._http_client.close()
                    self._http_client = None
                    self._api_client = None
        
        return self.async_show_form(
            step_id="user",
            data_schema=STEP_API_SCHEMA,
            errors=errors,
        )

    async def async_step_system_name(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle system name configuration."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            self._climate_system_name = user_input["climate_system_name"]
            
            # Fetch zones from API
            try:
                if not self._api_client:
                    raise ConfigurationError("API client not initialized")
                
                self._zones = await self._api_client.fetch_zones_configuration()
                
                if not self._zones:
                    errors["base"] = "no_zones_found"
                else:
                    # Move to zones configuration step
                    return await self.async_step_zones()
                    
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Failed to fetch zones")
                errors["base"] = "unknown"
        
        return self.async_show_form(
            step_id="system_name",
            data_schema=STEP_SYSTEM_SCHEMA,
            errors=errors
        )

    async def async_step_zones(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle zones configuration."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            # Update zone labels with user input
            zones_config = []
            for zone in self._zones:
                key = f"zone_{zone['base_id']}_{zone['zone_id']}"
                label = user_input.get(key, zone['label'])
                zones_config.append({
                    "base_id": zone['base_id'],
                    "zone_id": zone['zone_id'],
                    "label": label
                })
            
            # Create configuration data
            config_data = {
                "climate_system_name": self._climate_system_name,
                "api_url": self._api_url,
                "api_port": self._api_port,
                "zones": zones_config
            }
            
            # Validate configuration
            try:
                ConfigData.from_dict(config_data)
            except ValueError as err:
                _LOGGER.error("Configuration validation failed: %s", err)
                errors["base"] = "invalid_config"
            else:
                # Clean up HTTP client
                if self._http_client:
                    await self._http_client.close()
                
                # Create entry
                return self.async_create_entry(
                    title=f"{self._climate_system_name} Climate Control System",
                    data=config_data
                )
        
        # Build dynamic schema for zones
        zone_schema_dict = {}
        for zone in self._zones:
            key = f"zone_{zone['base_id']}_{zone['zone_id']}"
            zone_schema_dict[vol.Required(key, default=zone['label'])] = str
        
        zone_schema = vol.Schema(zone_schema_dict)
        
        return self.async_show_form(
            step_id="zones",
            data_schema=zone_schema,
            errors=errors,
            description_placeholders={
                "zones_count": str(len(self._zones))
            }
        )

    async def async_step_import(self, import_config: Dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        # Migration from old configuration format
        try:
            # Parse old format zones (comma-separated string) to new format
            old_zones = import_config.get("zones", "").split(",")
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
            
            # Convert to new format
            new_config = {
                "climate_system_name": import_config.get("climate_system_name", "Rehau Neasmart 2.0"),
                "api_url": import_config.get("neasmart_gw_server_host", ""),
                "api_port": import_config.get("neasmart_gw_server_port", 80),
                "zones": zones
            }
            
            # Validate configuration
            ConfigData.from_dict(new_config)
            
            # Create entry
            return self.async_create_entry(
                title=f"{new_config['climate_system_name']} Climate Control System",
                data=new_config
            )
            
        except Exception as err:
            _LOGGER.error("Failed to import configuration: %s", err)
            return self.async_abort(reason="invalid_config")