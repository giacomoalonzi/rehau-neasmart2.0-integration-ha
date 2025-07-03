"""Data models for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class OperationState(str, Enum):
    """Operation states for zones and global system."""
    NORMAL = "normal"
    REDUCED = "reduced"
    STANDBY = "standby"
    SCHEDULED = "scheduled"
    PARTY = "party"
    HOLIDAY = "holiday"


class TemperatureUnit(str, Enum):
    """Temperature units."""
    CELSIUS = "°C"
    FAHRENHEIT = "°F"


class HealthStatus(str, Enum):
    """System health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class BaseInfo:
    """Base station information."""
    id: int
    label: str
    
    def validate(self) -> None:
        """Validate base info."""
        if not 1 <= self.id <= 4:
            raise ValueError(f"Invalid base ID: {self.id}")


@dataclass
class ZoneInfo:
    """Zone information."""
    id: int
    label: str
    
    def validate(self) -> None:
        """Validate zone info."""
        if not 1 <= self.id <= 12:
            raise ValueError(f"Invalid zone ID: {self.id}")


@dataclass
class Temperature:
    """Temperature with unit."""
    value: float
    unit: TemperatureUnit = TemperatureUnit.CELSIUS
    
    def validate(self) -> None:
        """Validate temperature."""
        if not -50 <= self.value <= 100:
            raise ValueError(f"Invalid temperature value: {self.value}")


@dataclass
class Zone:
    """Zone data model."""
    base: BaseInfo
    zone: ZoneInfo
    state: OperationState
    temperature: Temperature
    setpoint: Optional[Temperature]
    relative_humidity: int
    address: int
    
    @property
    def unique_id(self) -> str:
        """Generate unique ID for the zone."""
        return f"{self.base.id}_{self.zone.id}"
    
    def validate(self) -> None:
        """Validate zone data."""
        self.base.validate()
        self.zone.validate()
        self.temperature.validate()
        if self.setpoint:
            self.setpoint.validate()
        if not 0 <= self.relative_humidity <= 100:
            raise ValueError(f"Invalid humidity: {self.relative_humidity}")


@dataclass
class ZonesListResponse:
    """Response model for zones list."""
    zones: List[Zone]
    count: int


@dataclass
class ZoneUpdateRequest:
    """Request model for zone update."""
    state: Optional[OperationState] = None
    setpoint: Optional[float] = None
    
    def validate(self) -> None:
        """Validate update request."""
        if self.state is None and self.setpoint is None:
            raise ValueError("At least one of state or setpoint must be provided")
        if self.setpoint is not None and not -50 <= self.setpoint <= 100:
            raise ValueError(f"Invalid setpoint value: {self.setpoint}")


@dataclass
class ZoneUpdateResponse:
    """Response model for zone update."""
    base: BaseInfo
    zone: ZoneInfo
    updated: Dict[str, any]


@dataclass
class OperationStateResponse:
    """Response model for operation state."""
    state: OperationState


@dataclass
class OperationStateUpdateRequest:
    """Request model for operation state update."""
    state: OperationState


@dataclass
class OperationStateUpdateResponse:
    """Response model for operation state update."""
    status: str
    state: OperationState


@dataclass
class HealthResponse:
    """System health response."""
    status: HealthStatus
    version: str
    database: Dict[str, any]
    modbus: Dict[str, any]
    configuration: Dict[str, any]


@dataclass
class DeviceInfo:
    """Device information."""
    id: str
    name: str
    manufacturer: str = "Rehau"
    model: str = ""
    
    @property
    def unique_id(self) -> str:
        """Return unique device ID."""
        return self.id


@dataclass
class ConfigData:
    """Configuration data model."""
    climate_system_name: str
    api_url: str
    api_port: int
    zones: List[Dict[str, any]]  # List of {base_id, zone_id, label}
    # These fields are commented out as they're not yet implemented in the API
    # mixed_groups: int = 0
    # pumps_regs_mapping: List[int] = field(default_factory=list)
    # dehumidificators_regs_mapping: List[int] = field(default_factory=list)

    def __post_init__(self):
        """Post initialization validation."""
        self.validate()

    def validate(self) -> None:
        """Validate configuration data."""
        # Validate climate system name
        if not self.climate_system_name:
            raise ValueError("Climate system name cannot be empty")
        
        # Validate API URL
        if not self.api_url:
            raise ValueError("API URL cannot be empty")
        
        # Validate API port
        if not 1 <= self.api_port <= 65535:
            raise ValueError(f"Invalid API port: {self.api_port}")
        
        # Validate zones
        if not self.zones:
            raise ValueError("At least one zone must be configured")
        if len(self.zones) > 48:
            raise ValueError("Maximum 48 zones allowed")
        
        # Validate each zone
        for zone in self.zones:
            base_id = zone.get("base_id")
            zone_id = zone.get("zone_id")
            label = zone.get("label")
            
            if base_id is None or zone_id is None or not label:
                raise ValueError("Each zone must have base_id, zone_id, and label")
            
            if not 1 <= base_id <= 4:
                raise ValueError(f"Invalid base_id: {base_id}")
            if not 1 <= zone_id <= 12:
                raise ValueError(f"Invalid zone_id: {zone_id}")

    @classmethod
    def from_dict(cls, data: Dict) -> ConfigData:
        """Create ConfigData from dictionary."""
        return cls(
            climate_system_name=data["climate_system_name"],
            api_url=data["api_url"],
            api_port=data["api_port"],
            zones=data["zones"]
        )


# Legacy models for backward compatibility during migration
# These will be removed in future versions
@dataclass
class LegacyPresetState:
    """Legacy preset states - mapped to new OperationState."""
    NORMAL = 1
    REDUCED = 2
    STANDBY = 3
    TIME_PROGRAM = 4  # Maps to SCHEDULED
    PARTY = 5
    ABSENCE = 6  # Maps to HOLIDAY
    
    @staticmethod
    def to_operation_state(legacy_state: int) -> OperationState:
        """Convert legacy state to new operation state."""
        mapping = {
            1: OperationState.NORMAL,
            2: OperationState.REDUCED,
            3: OperationState.STANDBY,
            4: OperationState.SCHEDULED,
            5: OperationState.PARTY,
            6: OperationState.HOLIDAY
        }
        return mapping.get(legacy_state, OperationState.NORMAL) 