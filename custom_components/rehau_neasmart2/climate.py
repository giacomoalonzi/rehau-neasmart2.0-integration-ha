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

from .const import DOMAIN
from .exceptions import DataValidationError
from .models import Zone, ZoneState

_LOGGER = logging.getLogger(__name__)

# Mapping between Home Assistant preset modes and API zone states
PRESET_MODE_MAPPING = {
    "presence": ZoneState.PRESENCE,
    "away": ZoneState.AWAY,
    "standby": ZoneState.STANDBY,
    "scheduled": ZoneState.SCHEDULED,
}

PRESET_MODE_MAPPING_REVERSE = {v: k for k, v in PRESET_MODE_MAPPING.items()}


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
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
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
        self._attr_preset_modes = list(PRESET_MODE_MAPPING.keys())
        self._attr_preset_mode = None
        
        # Temperature attributes
        self._attr_current_humidity: Optional[float] = None
        self._attr_current_temperature: Optional[float] = None
        self._attr_target_temperature: Optional[float] = None
        
        # Temperature limits
        self._attr_min_temp = 5.0
        self._attr_max_temp = 30.0
        self._attr_target_temperature_step = 0.5
        
        # Store zone data
        self._zone_data: Optional[Zone] = None

    async def async_update(self) -> None:
        """Update zone climate entity state."""
        try:
            zone_data = await self._device.get_zone_data()
            
            if zone_data is None:
                raise DataValidationError("No data received from zone")
            
            self._zone_data = zone_data
            
            # Update HVAC mode and preset mode based on zone state
            if zone_data.state == ZoneState.OFF:
                self._attr_hvac_mode = HVACMode.OFF
                self._attr_preset_mode = None
            else:
                self._attr_hvac_mode = HVACMode.AUTO
                self._attr_preset_mode = PRESET_MODE_MAPPING_REVERSE.get(zone_data.state)
            
            # Update measurements
            self._attr_current_humidity = float(zone_data.relative_humidity)
            self._attr_current_temperature = float(zone_data.temperature.value)
            
            # Update target temperature if available
            if zone_data.setpoint:
                self._attr_target_temperature = float(zone_data.setpoint.value)
            
            # Validate ranges
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
        if preset_mode not in PRESET_MODE_MAPPING:
            _LOGGER.error(
                "Invalid preset mode %s for %s",
                preset_mode,
                self._attr_unique_id
            )
            return
        
        try:
            zone_state = PRESET_MODE_MAPPING[preset_mode]
            success = await self._device.set_zone_state(zone_state)
            
            if success:
                self._attr_preset_mode = preset_mode
                self._attr_hvac_mode = HVACMode.AUTO
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

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        try:
            if hvac_mode == HVACMode.OFF:
                # Set zone to OFF state
                success = await self._device.set_zone_state(ZoneState.OFF)
                if success:
                    self._attr_hvac_mode = HVACMode.OFF
                    self._attr_preset_mode = None
                    self.async_write_ha_state()
            elif hvac_mode == HVACMode.AUTO:
                # Set zone to presence state (default active state)
                success = await self._device.set_zone_state(ZoneState.PRESENCE)
                if success:
                    self._attr_hvac_mode = HVACMode.AUTO
                    self._attr_preset_mode = "presence"
                    self.async_write_ha_state()
            else:
                _LOGGER.error("Unsupported HVAC mode %s for %s", hvac_mode, self._attr_unique_id)
        except Exception as err:
            _LOGGER.error("Error setting HVAC mode for %s: %s", self._attr_unique_id, err)

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

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        
        if self._zone_data:
            attrs["base_id"] = self._zone_data.base.id
            attrs["zone_id"] = self._zone_data.zone.id
            attrs["base_label"] = self._zone_data.base.label
            attrs["zone_label"] = self._zone_data.zone.label
            attrs["address"] = self._zone_data.address
            
            if self._zone_data.temperature:
                attrs["temperature_unit"] = self._zone_data.temperature.unit.value
        
        return attrs