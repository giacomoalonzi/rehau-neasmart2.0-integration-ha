"""Hub for Rehau Neasmart 2.0 Climate Control System."""
from __future__ import annotations

import logging
from typing import List, Optional

from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .exceptions import ConnectionError, DataValidationError
from .http_client import HttpClient, RehauNeasmart2ApiClient
from .models import ConfigData, DeviceInfo, SystemStatus, PresetState, ClimateMode

_LOGGER = logging.getLogger(__name__)


class RehauNeasmart2ClimateControlSystem:
    """Main hub for Rehau Neasmart 2.0 Climate Control System."""

    def __init__(
        self,
        hass: HomeAssistant,
        climate_system_name: str,
        neasmart_gw_server_host: str,
        neasmart_gw_server_port: int,
        zones: str,
        mixed_groups: int = 0,
        pumps_regs_mapping: str = "",
        dehumidificators_regs_mapping: str = ""
    ) -> None:
        """Initialize the climate control system hub."""
        self.hass = hass
        
        # Parse configuration
        config_dict = {
            "climate_system_name": climate_system_name,
            "neasmart_gw_server_host": neasmart_gw_server_host,
            "neasmart_gw_server_port": neasmart_gw_server_port,
            "zones": zones,
            "mixed_groups": mixed_groups,
            "pumps_regs_mapping": pumps_regs_mapping,
            "dehumidificators_regs_mapping": dehumidificators_regs_mapping
        }
        
        try:
            self.config = ConfigData.from_dict(config_dict)
        except ValueError as err:
            _LOGGER.error("Invalid configuration: %s", err)
            raise
        
        # Initialize device info
        self.device_info = DeviceInfo(
            id=climate_system_name,
            name=f"{climate_system_name} Climate Control System",
            manufacturer="Rehau",
            model="Neasmart 2.0 Base Station"
        )
        
        # Initialize HTTP client
        base_url = f"http://{self.config.neasmart_gw_server_host}:{self.config.neasmart_gw_server_port}"
        self._http_client = HttpClient(base_url)
        self._api_client = RehauNeasmart2ApiClient(self._http_client)
        
        # Status flags
        self.online = True
        self._system_status: Optional[SystemStatus] = None
        
        # Initialize devices
        self._init_devices()
    
    def _init_devices(self) -> None:
        """Initialize all devices."""
        # Initialize zones
        self.zones: List[RehauNeasmart2Zone] = []
        for i, zone_name in enumerate(self.config.zones):
            base_id = (i // 12) + 1
            zone_id = (i % 12) + 1
            zone = RehauNeasmart2Zone(self, base_id, zone_id, zone_name)
            self.zones.append(zone)
        
        # Initialize mixed groups
        self.mixgs: List[RehauNeasmart2MixedGroup] = [
            RehauNeasmart2MixedGroup(self, mixg_id)
            for mixg_id in range(1, self.config.mixed_groups + 1)
        ]
        
        # Initialize pumps
        self.pumps: List[RehauNeasmart2Pump] = [
            RehauNeasmart2Pump(self, pump_id)
            for pump_id in self.config.pumps_regs_mapping
        ]
        
        # Initialize dehumidifiers
        self.dehumidifiers: List[RehauNeasmart2Dehumidifier] = [
            RehauNeasmart2Dehumidifier(self, dehum_id)
            for dehum_id in self.config.dehumidificators_regs_mapping
        ]
    
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
        """Test connection to the shim server."""
        try:
            self.online = await self._http_client.health_check()
            return self.online
        except ConnectionError:
            self.online = False
            return False
    
    async def update_system_status(self) -> None:
        """Update system status."""
        try:
            # Get all system data in parallel
            outside_temp = await self.get_outside_temperature()
            filtered_temp = await self.get_filtered_outside_temperature()
            notifications = await self._api_client.get_notifications()
            global_state = await self.get_global_state()
            global_mode = await self.get_global_mode()
            
            self._system_status = SystemStatus(
                outside_temperature=outside_temp,
                filtered_outside_temperature=filtered_temp,
                hints_present=notifications["hints"],
                warnings_present=notifications["warnings"],
                errors_present=notifications["errors"],
                global_state=PresetState(global_state),
                global_mode=ClimateMode(global_mode)
            )
            self.online = True
        except (ConnectionError, DataValidationError) as err:
            _LOGGER.error("Failed to update system status: %s", err)
            self.online = False
    
    # Temperature methods
    async def get_outside_temperature(self) -> float:
        """Get outside temperature."""
        return await self._api_client.get_outside_temperature()
    
    async def get_filtered_outside_temperature(self) -> float:
        """Get filtered outside temperature."""
        return await self._api_client.get_filtered_outside_temperature()
    
    # Notification methods
    async def get_notification_hints(self) -> bool:
        """Get notification hints status."""
        notifications = await self._api_client.get_notifications()
        return notifications["hints"]
    
    async def get_notification_warnings(self) -> bool:
        """Get notification warnings status."""
        notifications = await self._api_client.get_notifications()
        return notifications["warnings"]
    
    async def get_notification_errors(self) -> bool:
        """Get notification errors status."""
        notifications = await self._api_client.get_notifications()
        return notifications["errors"]
    
    # Global state/mode methods
    async def get_global_state(self) -> int:
        """Get global state."""
        return await self._api_client.get_global_state()
    
    async def set_global_state(self, state: int) -> bool:
        """Set global state."""
        try:
            await self._api_client.set_global_state(state)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set global state: %s", err)
            return False
    
    async def get_global_mode(self) -> int:
        """Get global mode."""
        return await self._api_client.get_global_mode()
    
    async def set_global_mode(self, mode: int) -> bool:
        """Set global mode."""
        try:
            await self._api_client.set_global_mode(mode)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set global mode: %s", err)
            return False


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
    
    async def get_zone_data(self) -> dict | None:
        """Get zone data."""
        try:
            return await self.hub._api_client.get_zone_data(self.base_id, self.zone_id)
        except Exception as err:
            _LOGGER.error("Failed to get zone data for %s: %s", self.id, err)
            return None
    
    async def set_zone_setpoint(self, setpoint: float) -> bool:
        """Set zone setpoint temperature."""
        try:
            await self.hub._api_client.set_zone_setpoint(self.base_id, self.zone_id, setpoint)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set zone setpoint for %s: %s", self.id, err)
            return False
    
    async def set_zone_state(self, state: int) -> bool:
        """Set zone state."""
        try:
            await self.hub._api_client.set_zone_state(self.base_id, self.zone_id, state)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set zone state for %s: %s", self.id, err)
            return False


class RehauNeasmart2MixedGroup:
    """Rehau Neasmart 2.0 Mixed Group."""

    def __init__(self, hub: RehauNeasmart2ClimateControlSystem, mixg_id: int) -> None:
        """Initialize mixed group."""
        self.hub = hub
        self.mixg_id = mixg_id
        
        self.device_info = DeviceInfo(
            id=f"{hub.id}_{mixg_id}",
            name=f"Mixed Group #{mixg_id}",
            manufacturer="Rehau",
            model="Mixed Group w/ 24/230 Pump and 0-10v controlled mixing valve"
        )
    
    @property
    def id(self) -> str:
        """Return unique ID."""
        return self.device_info.id
    
    @property
    def name(self) -> str:
        """Return name."""
        return self.device_info.name
    
    @property
    def manufacturer(self) -> str:
        """Return manufacturer."""
        return self.device_info.manufacturer
    
    @property
    def model(self) -> str:
        """Return model."""
        return self.device_info.model
    
    async def get_flow_temperature(self) -> float | None:
        """Get flow temperature."""
        try:
            data = await self.hub._api_client.get_mixed_group_data(self.mixg_id)
            return data.get("flow_temperature")
        except Exception as err:
            _LOGGER.error("Failed to get flow temperature for %s: %s", self.id, err)
            return None
    
    async def get_return_temperature(self) -> float | None:
        """Get return temperature."""
        try:
            data = await self.hub._api_client.get_mixed_group_data(self.mixg_id)
            return data.get("return_temperature")
        except Exception as err:
            _LOGGER.error("Failed to get return temperature for %s: %s", self.id, err)
            return None
    
    async def get_valve_opening_percentage(self) -> int | None:
        """Get valve opening percentage."""
        try:
            data = await self.hub._api_client.get_mixed_group_data(self.mixg_id)
            return data.get("mixing_valve_opening_percentage")
        except Exception as err:
            _LOGGER.error("Failed to get valve opening for %s: %s", self.id, err)
            return None
    
    async def get_pump_state(self) -> int | None:
        """Get pump state."""
        try:
            data = await self.hub._api_client.get_mixed_group_data(self.mixg_id)
            return data.get("pump_state")
        except Exception as err:
            _LOGGER.error("Failed to get pump state for %s: %s", self.id, err)
            return None


class RehauNeasmart2Dehumidifier:
    """Rehau Neasmart 2.0 Dehumidifier."""

    def __init__(self, hub: RehauNeasmart2ClimateControlSystem, dehumidifier_id: int) -> None:
        """Initialize dehumidifier."""
        self.hub = hub
        self.dehumidifier_id = dehumidifier_id
        
        self.device_info = DeviceInfo(
            id=f"{hub.id}_{dehumidifier_id}",
            name=f"Dehumidifier #{dehumidifier_id}",
            manufacturer="Rehau",
            model="Dehumidifier with optional hydronic battery"
        )
    
    @property
    def id(self) -> str:
        """Return unique ID."""
        return self.device_info.id
    
    @property
    def name(self) -> str:
        """Return name."""
        return self.device_info.name
    
    @property
    def manufacturer(self) -> str:
        """Return manufacturer."""
        return self.device_info.manufacturer
    
    @property
    def model(self) -> str:
        """Return model."""
        return self.device_info.model
    
    async def get_dehumidifier_state(self) -> int | None:
        """Get dehumidifier state."""
        try:
            return await self.hub._api_client.get_dehumidifier_state(self.dehumidifier_id)
        except Exception as err:
            _LOGGER.error("Failed to get dehumidifier state for %s: %s", self.id, err)
            return None


class RehauNeasmart2Pump:
    """Rehau Neasmart 2.0 Extra Pump."""

    def __init__(self, hub: RehauNeasmart2ClimateControlSystem, pump_id: int) -> None:
        """Initialize pump."""
        self.hub = hub
        self.pump_id = pump_id
        
        self.device_info = DeviceInfo(
            id=f"{hub.id}_{pump_id}",
            name=f"Extra Pump #{pump_id}",
            manufacturer="Rehau",
            model="On-Off 24/230v Pump"
        )
    
    @property
    def id(self) -> str:
        """Return unique ID."""
        return self.device_info.id
    
    @property
    def name(self) -> str:
        """Return name."""
        return self.device_info.name
    
    @property
    def manufacturer(self) -> str:
        """Return manufacturer."""
        return self.device_info.manufacturer
    
    @property
    def model(self) -> str:
        """Return model."""
        return self.device_info.model
    
    async def get_pump_state(self) -> int | None:
        """Get pump state."""
        try:
            return await self.hub._api_client.get_pump_state(self.pump_id)
        except Exception as err:
            _LOGGER.error("Failed to get pump state for %s: %s", self.id, err)
            return None