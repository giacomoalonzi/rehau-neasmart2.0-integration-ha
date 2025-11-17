"""Select platform for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import logging
from typing import Any, List

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .models import OperationState

_LOGGER = logging.getLogger(__name__)

# Mapping for user-friendly names
OPERATION_STATE_OPTIONS = {
    "off": "Off",
    "presence": "Presence",
    "away": "Away",
    "standby": "Standby",
    "scheduled": "Scheduled",
    "party": "Party",
    "holiday": "Holiday",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: List[SelectEntity] = [
        RehauNeasmart2GlobalOperationStateSelect(hub)
    ]
    
    if entities:
        async_add_entities(entities)


class RehauNeasmart2GenericSelect(SelectEntity, RestoreEntity):
    """Base class for Rehau Neasmart2 select entities."""
    
    _attr_has_entity_name = False

    def __init__(self, device) -> None:
        """Initialize the generic select entity."""
        self._device = device
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
        return self._device.online and self._available

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


class RehauNeasmart2GlobalOperationStateSelect(RehauNeasmart2GenericSelect):
    """Select entity for global operation state."""

    def __init__(self, device) -> None:
        """Initialize the global operation state select entity."""
        super().__init__(device)
        self._attr_unique_id = f"{self._device.id}_global_operation_state"
        self._attr_name = f"{self._device.name} Global Operation State"
        self._attr_options = list(OPERATION_STATE_OPTIONS.keys())
        self._attr_current_option = None

    async def async_select_option(self, option: str) -> None:
        """Select a new operation state."""
        try:
            # Convert string option to OperationState enum
            operation_state = OperationState(option)
            
            success = await self._device.set_operation_state(operation_state)
            
            if success:
                self._attr_current_option = option
                self.async_write_ha_state()
                _LOGGER.info(
                    "Successfully set global operation state to %s",
                    OPERATION_STATE_OPTIONS[option]
                )
            else:
                _LOGGER.error(
                    "Failed to set global operation state to %s",
                    OPERATION_STATE_OPTIONS[option]
                )
        except ValueError:
            _LOGGER.error(
                "Invalid operation state option: %s",
                option
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting global operation state: %s",
                err
            )

    async def async_update(self) -> None:
        """Update the current operation state."""
        try:
            state = await self._device.get_operation_state()
            
            if state is not None:
                self._attr_current_option = state.value
                self._reset_error_count()
            else:
                raise ValueError("No operation state received")
                
        except Exception as err:
            self._handle_update_error(err)
            _LOGGER.error(
                "Error updating global operation state: %s",
                err
            )

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added."""
        await super().async_added_to_hass()
        
        # Restore previous state if available
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in self._attr_options:
                self._attr_current_option = last_state.state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        
        if self._attr_current_option:
            attrs["friendly_name"] = OPERATION_STATE_OPTIONS.get(
                self._attr_current_option,
                self._attr_current_option
            )
        
        return attrs