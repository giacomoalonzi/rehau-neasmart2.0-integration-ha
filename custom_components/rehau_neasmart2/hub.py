"""Hub for Rehau Neasmart 2.0 Climate Control System."""
from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .exceptions import ConnectionError, DataValidationError
from .http_client import HttpClient, RehauNeasmart2ApiClient
from .models import ConfigData, DeviceInfo, Zone, OperationState, HealthResponse

_LOGGER = logging.getLogger(__name__)


class RehauNeasmart2ClimateControlSystem:
    """Main hub for Rehau Neasmart 2.0 Climate Control System."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_data: Dict[str, Any]
    ) -> None:
        """Initialize the climate control system hub."""
        self.hass = hass
        
        # Parse configuration
        try:
            self.config = ConfigData.from_dict(config_data)
        except ValueError as err:
            _LOGGER.error("Invalid configuration: %s", err)
            raise
        
        # Initialize device info
        self.device_info = DeviceInfo(
            id=self.config.climate_system_name,
            name=f"{self.config.climate_system_name} Climate Control System",
            manufacturer="Rehau",
            model="Neasmart 2.0 Base Station"
        )
        
        # Initialize HTTP client
        self._http_client = HttpClient(
            self.config.api_url,
            self.config.api_port
        )
        self._api_client = RehauNeasmart2ApiClient(self._http_client)
        
        # Status flags
        self.online = True
        self._health_response: Optional[HealthResponse] = None
        self._operation_state: Optional[OperationState] = None
        
        # Initialize zones
        self._init_zones()
        
        # Commented out for future implementation
        # self._init_mixed_groups()
        # self._init_pumps()
        # self._init_dehumidifiers()
    
    def _init_zones(self) -> None:
        """Initialize all zones."""
        self.zones: List[RehauNeasmart2Zone] = []
        for zone_config in self.config.zones:
            zone = RehauNeasmart2Zone(
                self,
                zone_config["base_id"],
                zone_config["zone_id"],
                zone_config["label"]
            )
            self.zones.append(zone)
    
    # Commented out for future implementation
    # def _init_mixed_groups(self) -> None:
    #     """Initialize mixed groups when API support is available."""
    #     pass
    
    # def _init_pumps(self) -> None:
    #     """Initialize pumps when API support is available."""
    #     pass
    
    # def _init_dehumidifiers(self) -> None:
    #     """Initialize dehumidifiers when API support is available."""
    #     pass
    
    @property
    def id(self) -> str:
        """Return unique ID."""
        return self.device_info.id
    
    @property
    def name(self) -> str:
        """Return device name."""
        return self.device_info.name
    
    @property
    def manufacturer(self) -> str:
        """Return manufacturer."""
        return self.device_info.manufacturer
    
    @property
    def model(self) -> str:
        """Return model."""
        return self.device_info.model
    
    @property
    def hub(self) -> RehauNeasmart2ClimateControlSystem:
        """Return hub reference for compatibility."""
        return self
    
    async def async_init(self) -> None:
        """Async initialization."""
        await self._http_client.connect()
    
    async def async_close(self) -> None:
        """Close connections."""
        await self._http_client.close()
    
    async def test_connection(self) -> bool:
        """Test connection to the API server."""
        try:
            health = await self._api_client.health_check()
            self.online = health.status != "unhealthy"
            self._health_response = health
            return self.online
        except ConnectionError:
            self.online = False
            return False
    
    async def update_system_status(self) -> None:
        """Update system status."""
        try:
            # Get health status
            self._health_response = await self._api_client.health_check()
            
            # Get global operation state
            self._operation_state = await self._api_client.get_operation_state()
            
            self.online = True
        except (ConnectionError, DataValidationError) as err:
            _LOGGER.error("Failed to update system status: %s", err)
            self.online = False
    
    # Global operation state methods
    async def get_operation_state(self) -> OperationState:
        """Get global operation state."""
        return await self._api_client.get_operation_state()
    
    async def set_operation_state(self, state: OperationState) -> bool:
        """Set global operation state."""
        try:
            await self._api_client.set_operation_state(state)
            self._operation_state = state
            return True
        except Exception as err:
            _LOGGER.error("Failed to set operation state: %s", err)
            return False
    
    async def get_all_zones(self) -> List[Zone]:
        """Get all zones data from API."""
        try:
            return await self._api_client.get_zones()
        except Exception as err:
            _LOGGER.error("Failed to get all zones: %s", err)
            return []


class RehauNeasmart2Zone:
    """Rehau Neasmart 2.0 Zone."""

    def __init__(
        self,
        hub: RehauNeasmart2ClimateControlSystem,
        base_id: int,
        zone_id: int,
        name: str
    ) -> None:
        """Initialize zone."""
        self.hub = hub
        self.base_id = base_id
        self.zone_id = zone_id
        
        self.device_info = DeviceInfo(
            id=f"{hub.id}_{base_id}_{zone_id}",
            name=name,
            manufacturer="Rehau",
            model="Neasmart 2.0 Room Thermostat"
        )
        
        # Cache for zone data
        self._zone_data: Optional[Zone] = None
    
    @property
    def id(self) -> str:
        """Return unique ID."""
        return self.device_info.id
    
    @property
    def name(self) -> str:
        """Return zone name."""
        return self.device_info.name
    
    @property
    def manufacturer(self) -> str:
        """Return manufacturer."""
        return self.device_info.manufacturer
    
    @property
    def model(self) -> str:
        """Return model."""
        return self.device_info.model
    
    async def get_zone_data(self) -> Zone | None:
        """Get zone data."""
        try:
            self._zone_data = await self.hub._api_client.get_zone(self.base_id, self.zone_id)
            return self._zone_data
        except Exception as err:
            _LOGGER.error("Failed to get zone data for %s: %s", self.id, err)
            return None
    
    async def set_zone_setpoint(self, setpoint: float) -> bool:
        """Set zone setpoint temperature."""
        try:
            await self.hub._api_client.update_zone(
                self.base_id,
                self.zone_id,
                setpoint=setpoint
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set zone setpoint for %s: %s", self.id, err)
            return False
    
    async def set_zone_state(self, state: OperationState) -> bool:
        """Set zone state."""
        try:
            await self.hub._api_client.update_zone(
                self.base_id,
                self.zone_id,
                state=state
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to set zone state for %s: %s", self.id, err)
            return False
    
    async def update_zone(self, state: Optional[OperationState] = None, setpoint: Optional[float] = None) -> bool:
        """Update zone state and/or setpoint."""
        try:
            await self.hub._api_client.update_zone(
                self.base_id,
                self.zone_id,
                state=state,
                setpoint=setpoint
            )
            return True
        except Exception as err:
            _LOGGER.error("Failed to update zone %s: %s", self.id, err)
            return False


# Commented out for future implementation when API support is available
# class RehauNeasmart2MixedGroup:
#     """Rehau Neasmart 2.0 Mixed Group."""
#     pass
#
# class RehauNeasmart2Dehumidifier:
#     """Rehau Neasmart 2.0 Dehumidifier."""
#     pass
#
# class RehauNeasmart2Pump:
#     """Rehau Neasmart 2.0 Extra Pump."""
#     pass