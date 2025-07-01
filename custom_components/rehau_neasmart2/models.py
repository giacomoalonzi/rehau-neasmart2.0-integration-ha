"""Data models for Rehau Neasmart 2.0 integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import IntEnum


class PresetState(IntEnum):
    """Preset states for climate control."""
    NORMAL = 1
    REDUCED = 2
    STANDBY = 3
    TIME_PROGRAM = 4
    PARTY = 5
    ABSENCE = 6


class ClimateMode(IntEnum):
    """Climate modes for the system."""
    AUTO = 1
    HEATING = 2
    COOLING = 3
    FORCED_HEATING = 4
    FORCED_COOLING = 5


class BinaryStatus(IntEnum):
    """Binary status values."""
    OFF = 0
    ON = 1


@dataclass
class ZoneData:
    """Zone data model."""
    base_id: int
    zone_id: int
    name: str
    state: PresetState
    temperature: float
    setpoint: float
    relative_humidity: float
    
    @property
    def unique_id(self) -> str:
        """Generate unique ID for the zone."""
        return f"{base_id}_{zone_id}"

    def validate(self) -> None:
        """Validate zone data."""
        if not 1 <= self.base_id <= 4:
            raise ValueError(f"Invalid base_id: {self.base_id}")
        if not 1 <= self.zone_id <= 12:
            raise ValueError(f"Invalid zone_id: {self.zone_id}")
        if not -50 <= self.temperature <= 100:
            raise ValueError(f"Invalid temperature: {self.temperature}")
        if not 0 <= self.relative_humidity <= 100:
            raise ValueError(f"Invalid humidity: {self.relative_humidity}")


@dataclass
class MixedGroupData:
    """Mixed group data model."""
    mixg_id: int
    flow_temperature: float
    return_temperature: float
    mixing_valve_opening_percentage: int
    pump_state: BinaryStatus

    def validate(self) -> None:
        """Validate mixed group data."""
        if not 1 <= self.mixg_id <= 3:
            raise ValueError(f"Invalid mixg_id: {self.mixg_id}")
        if not 0 <= self.mixing_valve_opening_percentage <= 100:
            raise ValueError(f"Invalid valve opening: {self.mixing_valve_opening_percentage}")


@dataclass
class SystemStatus:
    """System status data model."""
    outside_temperature: float
    filtered_outside_temperature: float
    hints_present: bool
    warnings_present: bool
    errors_present: bool
    global_state: PresetState
    global_mode: ClimateMode


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
    neasmart_gw_server_host: str
    neasmart_gw_server_port: int
    zones: List[str]
    mixed_groups: int = 0
    pumps_regs_mapping: List[int] = field(default_factory=list)
    dehumidificators_regs_mapping: List[int] = field(default_factory=list)

    def __post_init__(self):
        """Post initialization validation."""
        self.validate()

    def validate(self) -> None:
        """Validate configuration data."""
        # Validate zones
        if not self.zones:
            raise ValueError("At least one zone must be configured")
        if len(self.zones) > 48:
            raise ValueError("Maximum 48 zones allowed")
        
        # Validate mixed groups
        if not 0 <= self.mixed_groups <= 3:
            raise ValueError("Mixed groups must be between 0 and 3")
        
        # Validate pumps
        if len(self.pumps_regs_mapping) > 5:
            raise ValueError("Maximum 5 extra pumps allowed")
        for pump_id in self.pumps_regs_mapping:
            if not 1 <= pump_id <= 5:
                raise ValueError(f"Invalid pump ID: {pump_id}")
        
        # Validate dehumidifiers
        if len(self.dehumidificators_regs_mapping) > 9:
            raise ValueError("Maximum 9 dehumidifiers allowed")
        for dehum_id in self.dehumidificators_regs_mapping:
            if not 1 <= dehum_id <= 9:
                raise ValueError(f"Invalid dehumidifier ID: {dehum_id}")

    @classmethod
    def from_dict(cls, data: Dict) -> ConfigData:
        """Create ConfigData from dictionary."""
        # Parse comma-separated strings to lists
        zones = [z.strip() for z in data["zones"].split(",") if z.strip()]
        
        pumps = []
        if data.get("pumps_regs_mapping"):
            pumps = [int(p) for p in data["pumps_regs_mapping"].split(",") if p]
        
        dehumidifiers = []
        if data.get("dehumidificators_regs_mapping"):
            dehumidifiers = [int(d) for d in data["dehumidificators_regs_mapping"].split(",") if d]
        
        return cls(
            climate_system_name=data["climate_system_name"],
            neasmart_gw_server_host=data["neasmart_gw_server_host"],
            neasmart_gw_server_port=data["neasmart_gw_server_port"],
            zones=zones,
            mixed_groups=data.get("mixed_groups", 0),
            pumps_regs_mapping=pumps,
            dehumidificators_regs_mapping=dehumidifiers
        ) 