"""HTTP client for Rehau Neasmart 2.0 API communication."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientError, ClientTimeout

from .exceptions import ConnectionError, CommandFailedError, DataValidationError
from .cache import DataCache
from .models import (
    Zone, ZonesListResponse, OperationState, OperationStateResponse,
    HealthResponse, HealthStatus, Temperature, BaseInfo, ZoneInfo, TemperatureUnit,
    ZoneState
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1
API_VERSION = "/api/"


class HttpClient:
    """HTTP client with retry logic and error handling."""

    def __init__(self, base_url: str, port: int, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize the HTTP client."""
        self.base_url = f"http://{base_url}:{port}"
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self) -> HttpClient:
        """Enter context manager."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager."""
        await self.close()

    async def connect(self) -> None:
        """Create HTTP session."""
        if not self._session:
            self._session = aiohttp.ClientSession(timeout=self.timeout)

    async def close(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def _request(
        self,
        method: str,
        endpoint: str,
        json: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        if not self._session:
            await self.connect()

        # Prepend API version to endpoint
        full_endpoint = f"{API_VERSION}{endpoint}"
        url = urljoin(self.base_url, full_endpoint.lstrip('/'))
        
        for attempt in range(MAX_RETRIES):
            try:
                _LOGGER.debug(
                    "Making %s request to %s (attempt %d/%d)",
                    method, url, attempt + 1, MAX_RETRIES
                )
                
                async with self._session.request(
                    method, url, json=json, **kwargs
                ) as response:
                    # Handle both success and error responses
                    if response.content_type == 'application/json':
                        data = await response.json()
                        
                        # Check for error responses
                        if response.status >= 400:
                            error_msg = data.get("error", "Unknown error")
                            error_details = data.get("details", {})
                            _LOGGER.debug(
                                "API error response: status=%s, error=%s, details=%s",
                                response.status, error_msg, error_details
                            )
                            if response.status == 503:
                                raise ConnectionError(f"Service unavailable at {url}: {error_msg}")
                            elif response.status == 404:
                                # Zone or resource not found - might be a permanent error
                                _LOGGER.warning(
                                    "Zone/resource not found (404) at %s: %s",
                                    url, error_msg
                                )
                                raise CommandFailedError(
                                    f"Resource not found (404) at {url}: {error_msg}"
                                )
                            elif response.status == 400:
                                # Bad request - likely a validation error
                                _LOGGER.warning(
                                    "Bad request (400) at %s: %s. Details: %s",
                                    url, error_msg, error_details
                                )
                                raise CommandFailedError(
                                    f"Bad request (400) at {url}: {error_msg}. Details: {error_details}"
                                )
                            else:
                                raise CommandFailedError(
                                    f"API error {response.status} at {url}: {error_msg}"
                                )
                        
                        return data
                    else:
                        response.raise_for_status()
                        return {"status": response.status}
                        
            except ClientError as err:
                _LOGGER.warning(
                    "Request failed (attempt %d/%d) to %s: %s",
                    attempt + 1, MAX_RETRIES, url, err
                )
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise ConnectionError(
                        f"Failed to connect to {url} after {MAX_RETRIES} attempts"
                    ) from err
            except Exception as err:
                _LOGGER.error("Unexpected error during request to %s: %s", url, err)
                raise ConnectionError(f"Unexpected error at {url}: {err}") from err

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, json: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return await self._request("POST", endpoint, json=json, **kwargs)


class RehauNeasmart2ApiClient:
    """API client for Rehau Neasmart 2.0 operations with caching."""

    def __init__(self, http_client: HttpClient) -> None:
        """Initialize API client."""
        self.http = http_client
        self._cache = DataCache()

    async def health_check(self) -> HealthResponse:
        """Check system health."""
        data = await self.http.get("/health")
        return HealthResponse(
            status=HealthStatus(data["status"]),
            version=data["version"],
            database=data["database"],
            modbus=data["modbus"],
            configuration=data["configuration"]
        )

    async def get_zones(self) -> List[Zone]:
        """Get all zones."""
        async def fetch():
            data = await self.http.get("/zones")
            _LOGGER.debug("Received zones list response: %s", data)
            zones = []
            for zone_data in data.get("zones", []):
                try:
                    zone = self._parse_zone(zone_data)
                    zones.append(zone)
                except DataValidationError as err:
                    _LOGGER.error("Failed to parse zone from list: %s", err)
                    continue
            return zones
        
        return await self._cache.get_or_fetch("zones_list", fetch)

    async def get_zone(self, base_id: int, zone_id: int) -> Zone:
        """Get specific zone information."""
        cache_key = f"zone_{base_id}_{zone_id}"
        
        async def fetch():
            try:
                data = await self.http.get(f"/zones/{base_id}/{zone_id}")
                _LOGGER.debug("Received zone %s/%s response: %s", base_id, zone_id, data)
                parsed_zone = self._parse_zone(data)
                _LOGGER.debug(
                    "Successfully parsed zone %s/%s: temp=%s, setpoint=%s, humidity=%s",
                    base_id, zone_id,
                    parsed_zone.temperature.value if parsed_zone.temperature else None,
                    parsed_zone.setpoint.value if parsed_zone.setpoint else None,
                    parsed_zone.relative_humidity
                )
                return parsed_zone
            except Exception as err:
                _LOGGER.error(
                    "Error fetching/parsing zone %s/%s: %s. Type: %s",
                    base_id, zone_id, err, type(err).__name__,
                    exc_info=True
                )
                # Don't cache errors - re-raise so caller can handle it
                raise
        
        try:
            return await self._cache.get_or_fetch(cache_key, fetch)
        except Exception as err:
            # Invalidate cache on error to prevent caching bad data
            self._cache.invalidate(cache_key)
            _LOGGER.debug("Invalidated cache for zone %s/%s due to error", base_id, zone_id)
            raise

    async def update_zone(
        self, 
        base_id: int, 
        zone_id: int, 
        state: Optional[ZoneState] = None,
        setpoint: Optional[float] = None
    ) -> Dict[str, Any]:
        """Update zone state and/or setpoint."""
        payload = {}
        if state is not None:
            payload["state"] = state.value
        if setpoint is not None:
            payload["setpoint"] = setpoint
        
        if not payload:
            raise ValueError("At least one of state or setpoint must be provided")
        
        response = await self.http.post(f"/zones/{base_id}/{zone_id}", payload)
        
        # Invalidate cache after update
        self._cache.invalidate(f"zone_{base_id}_{zone_id}")
        self._cache.invalidate("zones_list")
        
        return response

    async def get_operation_state(self) -> OperationState:
        """Get global operation state."""
        async def fetch():
            data = await self.http.get("/state")
            return OperationState(data["state"])
        
        return await self._cache.get_or_fetch("operation_state", fetch)

    async def set_operation_state(self, state: OperationState) -> Dict[str, Any]:
        """Set global operation state."""
        response = await self.http.post("/state", {"state": state.value})
        
        # Invalidate cache after update
        self._cache.invalidate("operation_state")
        
        return response

    async def fetch_zones_configuration(self) -> List[Dict[str, Any]]:
        """Fetch all zones configuration for setup wizard."""
        try:
            zones_data = await self.http.get("/zones")
            zones = []
            
            for zone_data in zones_data["zones"]:
                # Handle both nested format (base.id, zone.id) and flattened format (baseId, zoneId)
                if "base" in zone_data and "zone" in zone_data:
                    # Nested format
                    base_id = zone_data["base"]["id"]
                    zone_id = zone_data["zone"]["id"]
                    label = zone_data["zone"]["label"]
                elif "baseId" in zone_data and "zoneId" in zone_data:
                    # Flattened format
                    base_id = zone_data["baseId"]
                    zone_id = zone_data["zoneId"]
                    label = zone_data.get("zoneLabel", f"Zone {zone_id}")
                else:
                    _LOGGER.warning("Unknown zone data format: %s", zone_data)
                    continue
                
                zones.append({
                    "base_id": base_id,
                    "zone_id": zone_id,
                    "label": label,
                    "editable": True  # Allow user to edit label
                })
            
            return zones
        except Exception as err:
            _LOGGER.error("Failed to fetch zones configuration: %s", err)
            raise

    def _parse_zone(self, data: Dict[str, Any]) -> Zone:
        """Parse zone data from API response."""
        # DEBUG: Log raw data to see what we're receiving from API
        _LOGGER.debug("Parsing zone data. Raw API response: %s", data)
        
        try:
            # Handle both nested format (base.id, zone.id) and flattened format (baseId, zoneId)
            if "base" in data and "zone" in data:
                # Nested format
                base = BaseInfo(
                    id=data["base"]["id"],
                    label=data["base"]["label"]
                )
                
                zone_info = ZoneInfo(
                    id=data["zone"]["id"],
                    label=data["zone"]["label"]
                )
            elif "baseId" in data and "zoneId" in data:
                # Flattened format
                base = BaseInfo(
                    id=data["baseId"],
                    label=data.get("baseLabel", f"Base {data['baseId']}")
                )
                
                zone_info = ZoneInfo(
                    id=data["zoneId"],
                    label=data.get("zoneLabel", f"Zone {data['zoneId']}")
                )
            else:
                raise DataValidationError(
                    f"Invalid zone data structure: missing base/zone or baseId/zoneId fields. "
                    f"Received: {list(data.keys())}"
                )
            
            # Safely parse temperature
            temp_data = data.get("temperature")
            _LOGGER.debug("Temperature data for zone %s: %s", zone_info.id, temp_data)
            
            # Check if temperature exists (handle 0 as valid value)
            if temp_data is None:
                raise DataValidationError(
                    f"Missing temperature data for zone {zone_info.id}. "
                    f"Available keys: {list(data.keys())}"
                )
            
            # Handle both object format {"value": 21.5, "unit": "°C"} and direct numeric value
            if isinstance(temp_data, dict):
                if temp_data.get("value") is None:
                    raise DataValidationError(
                        f"Missing temperature value for zone {zone_info.id}. "
                        f"Temperature object: {temp_data}"
                    )
                temperature = Temperature(
                    value=float(temp_data["value"]),
                    unit=TemperatureUnit(temp_data.get("unit", "°C"))
                )
            elif isinstance(temp_data, (int, float)):
                # Direct numeric value
                _LOGGER.debug("Temperature is direct numeric value: %s", temp_data)
                temperature = Temperature(
                    value=float(temp_data),
                    unit=TemperatureUnit("°C")
                )
            else:
                raise DataValidationError(
                    f"Invalid temperature format for zone {zone_info.id}: {type(temp_data)} - {temp_data}"
                )
            
            # Safely parse setpoint
            setpoint = None
            setpoint_data = data.get("setpoint")
            _LOGGER.debug("Setpoint data for zone %s: %s", zone_info.id, setpoint_data)
            
            if setpoint_data is not None:
                if isinstance(setpoint_data, dict):
                    # Handle object format {"value": 21.5, "unit": "°C"}
                    setpoint_value = setpoint_data.get("value")
                    if setpoint_value is not None:
                        setpoint = Temperature(
                            value=float(setpoint_value),
                            unit=TemperatureUnit(setpoint_data.get("unit", "°C"))
                        )
                elif isinstance(setpoint_data, (int, float)):
                    # Direct numeric value (including negative values like -17.7 which might indicate "off")
                    _LOGGER.debug("Setpoint is direct numeric value: %s", setpoint_data)
                    # Negative setpoint values are valid (e.g., -17.7 might indicate zone is off)
                    setpoint = Temperature(
                        value=float(setpoint_data),
                        unit=TemperatureUnit("°C")
                    )
                else:
                    _LOGGER.warning(
                        "Invalid setpoint format for zone %s: %s (type: %s). Ignoring.",
                        zone_info.id, setpoint_data, type(setpoint_data)
                    )
            
            # Parse state - handle both object format and string format
            state_data = data.get("state")
            _LOGGER.debug("State data for zone %s: %s", zone_info.id, state_data)
            
            if isinstance(state_data, dict):
                # New format: {"state": "presence"}
                zone_state = ZoneState(state_data["state"])
            elif isinstance(state_data, str):
                # Legacy format: "presence" (string directly)
                zone_state = ZoneState(state_data)
            else:
                raise DataValidationError(
                    f"Invalid state format for zone {zone_info.id}: {type(state_data)} - {state_data}"
                )
            
            # Safely parse relative_humidity - handle both snake_case and camelCase
            # Check both formats, handling 0 as a valid value
            relative_humidity = None
            if "relative_humidity" in data:
                relative_humidity = data["relative_humidity"]
            elif "relativeHumidity" in data:
                relative_humidity = data["relativeHumidity"]
            
            _LOGGER.debug("Humidity data for zone %s: %s", zone_info.id, relative_humidity)
            
            if relative_humidity is None:
                _LOGGER.warning(
                    "Missing relative_humidity for zone %s. Available keys: %s. Defaulting to 0",
                    zone_info.id, list(data.keys())
                )
                relative_humidity = 0
            
            parsed_zone = Zone(
                base=base,
                zone=zone_info,
                state=zone_state,
                temperature=temperature,
                setpoint=setpoint,
                relative_humidity=int(relative_humidity)
            )
            
            _LOGGER.debug(
                "Successfully parsed zone %s/%s: temp=%.1f°C, setpoint=%s, humidity=%d%%, state=%s",
                base.id, zone_info.id,
                temperature.value,
                f"{setpoint.value:.1f}°C" if setpoint else "None",
                relative_humidity,
                zone_state.value
            )
            
            return parsed_zone
        except (KeyError, TypeError, ValueError) as err:
            _LOGGER.error("Failed to parse zone data: %s. Raw data: %s", err, data)
            raise DataValidationError(f"Invalid zone data structure: {err}") from err

    def invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate cache entries."""
        self._cache.invalidate(key) 