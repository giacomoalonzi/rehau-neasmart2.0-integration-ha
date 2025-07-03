"""Sensor platform for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN
from .models import Zone

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from a config entry."""
    hub = hass.data[DOMAIN][config_entry.entry_id]
    
    entities: List[SensorEntity] = []
    
    # Add zone sensors
    for zone in hub.zones:
        entities.extend([
            RehauNeasmart2ZoneTemperatureSensor(zone),
            RehauNeasmart2ZoneHumiditySensor(zone),
            RehauNeasmart2ZoneSetpointSensor(zone),
        ])
    
    # Add system sensors
    entities.extend([
        RehauNeasmart2SystemHealthSensor(hub),
        RehauNeasmart2SystemVersionSensor(hub),
    ])
    
    # Future implementation - commented out
    # for mixg in hub.mixgs:
    #     entities.extend([
    #         RehauNeasmart2MixedGroupFlowTemperatureSensor(mixg),
    #         RehauNeasmart2MixedGroupReturnTemperatureSensor(mixg),
    #         RehauNeasmart2MixedGroupValveOpeningSensor(mixg),
    #         RehauNeasmart2MixedGroupPumpStateSensor(mixg),
    #     ])
    
    if entities:
        async_add_entities(entities)


class RehauNeasmart2GenericSensor(SensorEntity, RestoreEntity):
    """Base class for Rehau Neasmart2 sensor entities."""
    
    _attr_has_entity_name = False

    def __init__(self, device) -> None:
        """Initialize the sensor."""
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


class RehauNeasmart2ZoneTemperatureSensor(RehauNeasmart2GenericSensor):
    """Zone temperature sensor."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{self._device.id}_zone_temperature"
        self._attr_name = f"{self._device.name} Temperature"
        self._zone_data: Optional[Zone] = None

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            zone_data = await self._device.get_zone_data()
            if zone_data is not None:
                self._zone_data = zone_data
                self._attr_native_value = zone_data.temperature.value
                self._reset_error_count()
            else:
                raise ValueError("No zone data received")
        except Exception as err:
            self._handle_update_error(err)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        if self._zone_data and self._zone_data.temperature:
            attrs["unit"] = self._zone_data.temperature.unit.value
        return attrs


class RehauNeasmart2ZoneHumiditySensor(RehauNeasmart2GenericSensor):
    """Zone humidity sensor."""
    
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{self._device.id}_zone_humidity"
        self._attr_name = f"{self._device.name} Humidity"

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            zone_data = await self._device.get_zone_data()
            if zone_data is not None:
                self._attr_native_value = zone_data.relative_humidity
                self._reset_error_count()
            else:
                raise ValueError("No zone data received")
        except Exception as err:
            self._handle_update_error(err)


class RehauNeasmart2ZoneSetpointSensor(RehauNeasmart2GenericSensor):
    """Zone setpoint temperature sensor."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{self._device.id}_zone_setpoint"
        self._attr_name = f"{self._device.name} Setpoint"
        self._zone_data: Optional[Zone] = None

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            zone_data = await self._device.get_zone_data()
            if zone_data is not None:
                self._zone_data = zone_data
                if zone_data.setpoint:
                    self._attr_native_value = zone_data.setpoint.value
                else:
                    self._attr_native_value = None
                self._reset_error_count()
            else:
                raise ValueError("No zone data received")
        except Exception as err:
            self._handle_update_error(err)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        if self._zone_data and self._zone_data.setpoint:
            attrs["unit"] = self._zone_data.setpoint.unit.value
        return attrs


class RehauNeasmart2SystemHealthSensor(RehauNeasmart2GenericSensor):
    """System health sensor."""
    
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["healthy", "degraded", "unhealthy"]

    def __init__(self, device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{self._device.id}_system_health"
        self._attr_name = f"{self._device.name} System Health"

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            if self._device._health_response:
                self._attr_native_value = self._device._health_response.status.value
                self._reset_error_count()
            else:
                # Trigger a health check update
                await self._device.update_system_status()
                if self._device._health_response:
                    self._attr_native_value = self._device._health_response.status.value
                else:
                    raise ValueError("No health data received")
        except Exception as err:
            self._handle_update_error(err)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = {}
        if self._device._health_response:
            health = self._device._health_response
            attrs["database_healthy"] = health.database.get("healthy", False)
            attrs["modbus_healthy"] = health.modbus.get("healthy", False)
            if health.modbus.get("circuit_breaker"):
                attrs["circuit_breaker_state"] = health.modbus["circuit_breaker"].get("state")
                attrs["circuit_breaker_failures"] = health.modbus["circuit_breaker"].get("failures")
        return attrs


class RehauNeasmart2SystemVersionSensor(RehauNeasmart2GenericSensor):
    """System version sensor."""
    
    def __init__(self, device) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._attr_unique_id = f"{self._device.id}_system_version"
        self._attr_name = f"{self._device.name} API Version"

    async def async_update(self) -> None:
        """Update the sensor."""
        try:
            if self._device._health_response:
                self._attr_native_value = self._device._health_response.version
                self._reset_error_count()
            else:
                # Trigger a health check update
                await self._device.update_system_status()
                if self._device._health_response:
                    self._attr_native_value = self._device._health_response.version
                else:
                    raise ValueError("No health data received")
        except Exception as err:
            self._handle_update_error(err)