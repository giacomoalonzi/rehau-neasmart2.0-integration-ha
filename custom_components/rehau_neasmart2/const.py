"""Constants for the Rehau Neasmart 2.0 integration."""
from __future__ import annotations

from typing import Dict

from .models import PresetState, ClimateMode, BinaryStatus

DOMAIN = "rehau_neasmart2"

# Configuration constants
MAX_ZONES = 48
MAX_MIXED_GROUPS = 3
MAX_DEHUMIDIFIERS = 9
MAX_EXTRA_PUMPS = 5

# Value mappings
BINARY_STATUSES: Dict[int, str] = {
    BinaryStatus.OFF: "Off",
    BinaryStatus.ON: "On"
}

PRESENCE_STATES: Dict[bool, str] = {
    True: "Present",
    False: "Not Present"
}

PRESET_STATES_MAPPING: Dict[str, PresetState] = {
    "Normal": PresetState.NORMAL,
    "Reduced": PresetState.REDUCED,
    "Standby": PresetState.STANDBY,
    "Time Program": PresetState.TIME_PROGRAM,
    "Party": PresetState.PARTY,
    "Absence": PresetState.ABSENCE
}

PRESET_STATES_MAPPING_REVERSE: Dict[PresetState, str] = {
    v: k for k, v in PRESET_STATES_MAPPING.items()
}

PRESET_CLIMATE_MODES_MAPPING: Dict[str, ClimateMode] = {
    "Auto": ClimateMode.AUTO,
    "Heating": ClimateMode.HEATING,
    "Cooling": ClimateMode.COOLING,
    "Forced Heating": ClimateMode.FORCED_HEATING,
    "Forced Cooling": ClimateMode.FORCED_COOLING
}

PRESET_CLIMATE_MODES_MAPPING_REVERSE: Dict[ClimateMode, str] = {
    v: k for k, v in PRESET_CLIMATE_MODES_MAPPING.items()
}
