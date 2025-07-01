"""Config flow for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import logging
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from . import hub
from .const import DOMAIN, MAX_ZONES, MAX_MIXED_GROUPS, MAX_DEHUMIDIFIERS, MAX_EXTRA_PUMPS
from .exceptions import ConnectionError, ConfigurationError
from .models import ConfigData

_LOGGER = logging.getLogger(__name__)

# Define the schema for user input during the configuration flow.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("climate_system_name"): str,
        vol.Required("neasmart_gw_server_host"): str,
        vol.Required("neasmart_gw_server_port", default=80): vol.Coerce(int),
        vol.Required("zones"): str,
        vol.Optional("mixed_groups", default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=MAX_MIXED_GROUPS)
        ),
        vol.Optional("dehumidificators_regs_mapping", default=""): str,
        vol.Optional("pumps_regs_mapping", default=""): str,
    }
)


async def validate_input(hass: HomeAssistant, data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the user input allows us to connect."""
    
    # Validate configuration using ConfigData model
    try:
        config = ConfigData.from_dict(data)
    except ValueError as err:
        _LOGGER.error("Configuration validation failed: %s", err)
        raise ConfigurationError(str(err)) from err
    
    # Create hub instance to test connection
    neasmart_climate_control_hub = hub.RehauNeasmart2ClimateControlSystem(
        hass,
        data["climate_system_name"],
        data["neasmart_gw_server_host"],
        data["neasmart_gw_server_port"],
        data["zones"],
        data.get("mixed_groups", 0),
        data.get("dehumidificators_regs_mapping", ""),
        data.get("pumps_regs_mapping", "")
    )
    
    # Initialize and test connection
    await neasmart_climate_control_hub.async_init()
    
    try:
        if not await neasmart_climate_control_hub.test_connection():
            raise ConnectionError("Unable to connect to Neasmart gateway")
    finally:
        # Always close the connection
        await neasmart_climate_control_hub.async_close()
    
    return {"title": f"{data['climate_system_name']} Climate Control System"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Rehau Neasmart 2.0."""

    VERSION = 1

    async def async_step_user(
        self, user_input: Dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        
        if user_input is not None:
            try:
                # Validate the user input
                info = await validate_input(self.hass, user_input)
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except ConfigurationError as err:
                # Map specific validation errors to user-friendly messages
                error_msg = str(err).lower()
                if "zones" in error_msg and "48" in error_msg:
                    errors["base"] = "too_many_zones"
                elif "mixed groups" in error_msg:
                    errors["base"] = "too_many_mixg"
                elif "dehumidifiers" in error_msg and "9" in error_msg:
                    errors["base"] = "too_many_dehumidificators"
                elif "dehumidifier id" in error_msg:
                    errors["base"] = "invalid_dehumidificator_index"
                elif "pumps" in error_msg and "5" in error_msg:
                    errors["base"] = "too_many_extra_pump"
                elif "pump id" in error_msg:
                    errors["base"] = "invalid_pump_index"
                else:
                    errors["base"] = "unknown"
                    _LOGGER.error("Configuration error: %s", err)
            except Exception as err:
                _LOGGER.exception("Unexpected exception during validation")
                errors["base"] = "unknown"
            else:
                # Create a new entry if validation is successful
                return self.async_create_entry(title=info["title"], data=user_input)
        
        # Show the form to the user with any validation errors
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )