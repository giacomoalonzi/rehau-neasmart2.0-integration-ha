"""Climate platform for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, PRESET_STATES_MAPPING, PRESET_STATES_MAPPING_REVERSE
from .exceptions import DataValidationError
from .models import PresetState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: List[ClimateEntity] = [
        RehauNeasmart2ZoneClimateEntity(zone) for zone in hub.zones
    ]
    
    if entities:
        async_add_entities(entities)


class RehauNeasmart2GenericClimateEntity(ClimateEntity, RestoreEntity):
    """Base class for Rehau Neasmart2 climate entities."""
    
    _attr_has_entity_name = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO]
    _attr_hvac_mode = HVACMode.AUTO

    def __init__(self, device) -> None:
        """Initialize the climate entity."""
        self._device = device
        self._attr_unique_id = f"{device.id}_thermostat"
        self._attr_name = f"{device.name} Thermostat"
        
        # State variables
        self._available = True
        self._update_error_count = 0
        self._max_errors = 3

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device.id)},
            name=self._device.name,
            manufacturer=self._device.manufacturer,
            model=self._device.model,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._device.hub.online and self._available

    def _handle_update_error(self, error: Exception) -> None:
        """Handle update errors with retry logic."""
        self._update_error_count += 1
        if self._update_error_count >= self._max_errors:
            self._available = False
            _LOGGER.error(
                "Too many errors for %s, marking as unavailable: %s",
                self._attr_unique_id,
                error
            )
        else:
            _LOGGER.warning(
                "Error updating %s (attempt %d/%d): %s",
                self._attr_unique_id,
                self._update_error_count,
                self._max_errors,
                error
            )

    def _reset_error_count(self) -> None:
        """Reset error count on successful update."""
        if self._update_error_count > 0:
            self._update_error_count = 0
            self._available = True


class RehauNeasmart2ZoneClimateEntity(RehauNeasmart2GenericClimateEntity):
    """Climate entity for Rehau Neasmart2 zones."""

    def __init__(self, device) -> None:
        """Initialize zone climate entity."""
        super().__init__(device)
        
        # Add zone-specific features
        self._attr_supported_features = (
            ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TARGET_TEMPERATURE
        )
        
        # Preset modes
        self._attr_preset_modes = list(PRESET_STATES_MAPPING.keys())
        self._attr_preset_mode = None
        
        # Temperature attributes
        self._attr_current_humidity: Optional[float] = None
        self._attr_current_temperature: Optional[float] = None
        self._attr_target_temperature: Optional[float] = None
        
        # Temperature limits
        self._attr_min_temp = 5.0
        self._attr_max_temp = 30.0
        self._attr_target_temperature_step = 0.5

    async def async_update(self) -> None:
        """Update zone climate entity state."""
        try:
            zone_data = await self._device.get_zone_data()
            
            if zone_data is None:
                raise DataValidationError("No data received from zone")
            
            # Validate required fields
            required_fields = ["state", "relative_humidity", "temperature", "setpoint"]
            missing_fields = [f for f in required_fields if f not in zone_data]
            if missing_fields:
                raise DataValidationError(f"Missing fields in zone data: {missing_fields}")
            
            # Update state from zone data
            try:
                state = PresetState(zone_data["state"])
                self._attr_preset_mode = PRESET_STATES_MAPPING_REVERSE.get(state)
            except ValueError:
                _LOGGER.warning(
                    "Unknown state value %s for %s",
                    zone_data["state"],
                    self._attr_unique_id
                )
            
            # Update measurements
            self._attr_current_humidity = float(zone_data["relative_humidity"])
            self._attr_current_temperature = float(zone_data["temperature"])
            self._attr_target_temperature = float(zone_data["setpoint"])
            
            # Validate temperature ranges
            if not -50 <= self._attr_current_temperature <= 100:
                _LOGGER.warning(
                    "Temperature %s out of range for %s",
                    self._attr_current_temperature,
                    self._attr_unique_id
                )
            
            if not 0 <= self._attr_current_humidity <= 100:
                _LOGGER.warning(
                    "Humidity %s out of range for %s",
                    self._attr_current_humidity,
                    self._attr_unique_id
                )
            
            self._reset_error_count()
            
        except Exception as err:
            self._handle_update_error(err)
            _LOGGER.error(
                "Error updating %s thermostat: %s",
                self._attr_unique_id,
                err
            )

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode not in PRESET_STATES_MAPPING:
            _LOGGER.error(
                "Invalid preset mode %s for %s",
                preset_mode,
                self._attr_unique_id
            )
            return
        
        try:
            state_value = PRESET_STATES_MAPPING[preset_mode]
            success = await self._device.set_zone_state(state_value)
            
            if success:
                self._attr_preset_mode = preset_mode
                self.async_write_ha_state()
            else:
                _LOGGER.error(
                    "Failed to set preset mode %s for %s",
                    preset_mode,
                    self._attr_unique_id
                )
                
        except Exception as err:
            _LOGGER.error(
                "Error setting preset mode for %s: %s",
                self._attr_unique_id,
                err
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        
        if temperature is None:
            _LOGGER.error("No temperature provided for %s", self._attr_unique_id)
            return
        
        # Validate temperature range
        if not self._attr_min_temp <= temperature <= self._attr_max_temp:
            _LOGGER.error(
                "Temperature %s out of range [%s, %s] for %s",
                temperature,
                self._attr_min_temp,
                self._attr_max_temp,
                self._attr_unique_id
            )
            return
        
        try:
            success = await self._device.set_zone_setpoint(float(temperature))
            
            if success:
                self._attr_target_temperature = float(temperature)
                self.async_write_ha_state()
            else:
                _LOGGER.error(
                    "Failed to set temperature %s for %s",
                    temperature,
                    self._attr_unique_id
                )
                
        except Exception as err:
            _LOGGER.error(
                "Error setting temperature for %s: %s",
                self._attr_unique_id,
                err
            )

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.attributes.get("temperature"):
                self._attr_target_temperature = float(
                    last_state.attributes["temperature"]
                )
            if last_state.attributes.get("preset_mode"):
                self._attr_preset_mode = last_state.attributes["preset_mode"]