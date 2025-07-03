"""Constants for the Rehau Neasmart 2.0 integration."""
from __future__ import annotations

DOMAIN = "rehau_neasmart2"

# Configuration constants
MAX_ZONES = 48  # Maximum 4 bases * 12 zones per base
MAX_BASE_STATIONS = 4
MAX_ZONES_PER_BASE = 12

# Future implementation constants (commented out)
# MAX_MIXED_GROUPS = 3
# MAX_DEHUMIDIFIERS = 9
# MAX_EXTRA_PUMPS = 5

# Update intervals (in seconds)
DEFAULT_SCAN_INTERVAL = 30
FAST_SCAN_INTERVAL = 10
SLOW_SCAN_INTERVAL = 60

# Cache expiration times (in seconds)
CACHE_EXPIRATION_SHORT = 10
CACHE_EXPIRATION_MEDIUM = 30
CACHE_EXPIRATION_LONG = 300

# Temperature limits
MIN_TEMPERATURE = 5.0
MAX_TEMPERATURE = 30.0
TEMPERATURE_STEP = 0.5

# API version
API_VERSION = "2.1.0"

# Integration version
INTEGRATION_VERSION = "2.0.0"
