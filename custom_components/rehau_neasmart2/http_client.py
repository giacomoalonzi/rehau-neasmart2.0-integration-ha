"""HTTP client for Rehau Neasmart 2.0 shim server communication."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientError, ClientTimeout

from .exceptions import ConnectionError, CommandFailedError, DataValidationError
from .cache import DataCache

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_DELAY = 1


class HttpClient:
    """HTTP client with retry logic and error handling."""

    def __init__(self, base_url: str, timeout: int = DEFAULT_TIMEOUT) -> None:
        """Initialize the HTTP client."""
        self.base_url = base_url
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

        url = urljoin(self.base_url, endpoint)
        
        for attempt in range(MAX_RETRIES):
            try:
                _LOGGER.debug(
                    "Making %s request to %s (attempt %d/%d)",
                    method, url, attempt + 1, MAX_RETRIES
                )
                
                async with self._session.request(
                    method, url, json=json, **kwargs
                ) as response:
                    response.raise_for_status()
                    
                    if response.content_type == 'application/json':
                        return await response.json()
                    else:
                        # For non-JSON responses, return status info
                        return {"status": response.status}
                        
            except ClientError as err:
                _LOGGER.warning(
                    "Request failed (attempt %d/%d): %s",
                    attempt + 1, MAX_RETRIES, err
                )
                
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise ConnectionError(
                        f"Failed to connect to {url} after {MAX_RETRIES} attempts"
                    ) from err
            except Exception as err:
                _LOGGER.error("Unexpected error during request: %s", err)
                raise ConnectionError(f"Unexpected error: {err}") from err

    async def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make GET request."""
        return await self._request("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, json: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Make POST request."""
        return await self._request("POST", endpoint, json=json, **kwargs)

    async def health_check(self) -> bool:
        """Check if the server is healthy."""
        try:
            response = await self.get("/health")
            return response.get("status") == 200
        except ConnectionError:
            return False


class RehauNeasmart2ApiClient:
    """API client for Rehau Neasmart 2.0 operations with caching."""

    def __init__(self, http_client: HttpClient) -> None:
        """Initialize API client."""
        self.http = http_client
        self._cache = DataCache()

    async def get_outside_temperature(self) -> float:
        """Get outside temperature."""
        async def fetch():
            try:
                data = await self.http.get("/outsidetemperature")
                temp = data.get("outside_temperature")
                if temp is None:
                    raise DataValidationError("Missing outside_temperature in response")
                return float(temp)
            except (ValueError, TypeError) as err:
                raise DataValidationError(f"Invalid temperature value: {err}") from err
        
        return await self._cache.get_or_fetch("outside_temperature", fetch)

    async def get_filtered_outside_temperature(self) -> float:
        """Get filtered outside temperature."""
        async def fetch():
            try:
                data = await self.http.get("/outsidetemperature")
                temp = data.get("filtered_outside_temperature")
                if temp is None:
                    raise DataValidationError("Missing filtered_outside_temperature in response")
                return float(temp)
            except (ValueError, TypeError) as err:
                raise DataValidationError(f"Invalid temperature value: {err}") from err
        
        return await self._cache.get_or_fetch("filtered_outside_temperature", fetch)

    async def get_notifications(self) -> Dict[str, bool]:
        """Get all notifications status."""
        async def fetch():
            data = await self.http.get("/notifications")
            return {
                "hints": bool(data.get("hints_present", False)),
                "warnings": bool(data.get("warnings_present", False)),
                "errors": bool(data.get("error_present", False))
            }
        
        return await self._cache.get_or_fetch("notifications", fetch)

    async def get_global_state(self) -> int:
        """Get global state."""
        async def fetch():
            data = await self.http.get("/state")
            state = data.get("state")
            if state is None:
                raise DataValidationError("Missing state in response")
            return int(state)
        
        return await self._cache.get_or_fetch("global_state", fetch)

    async def set_global_state(self, state: int) -> None:
        """Set global state."""
        response = await self.http.post("/state", {"state": state})
        if response.get("status") != 202:
            raise CommandFailedError(f"Failed to set global state to {state}")
        # Invalidate cache after state change
        self._cache.invalidate("global_state")

    async def get_global_mode(self) -> int:
        """Get global mode."""
        async def fetch():
            data = await self.http.get("/mode")
            mode = data.get("mode")
            if mode is None:
                raise DataValidationError("Missing mode in response")
            return int(mode)
        
        return await self._cache.get_or_fetch("global_mode", fetch)

    async def set_global_mode(self, mode: int) -> None:
        """Set global mode."""
        response = await self.http.post("/mode", {"mode": mode})
        if response.get("status") != 202:
            raise CommandFailedError(f"Failed to set global mode to {mode}")
        # Invalidate cache after mode change
        self._cache.invalidate("global_mode")

    async def get_zone_data(self, base_id: int, zone_id: int) -> Dict[str, Any]:
        """Get zone data."""
        cache_key = f"zone_{base_id}_{zone_id}"
        
        async def fetch():
            data = await self.http.get(f"/zones/{base_id}/{zone_id}")
            
            # Validate required fields
            required_fields = ["state", "relative_humidity", "temperature", "setpoint"]
            for field in required_fields:
                if field not in data:
                    raise DataValidationError(f"Missing required field '{field}' in zone data")
            
            return data
        
        return await self._cache.get_or_fetch(cache_key, fetch)

    async def set_zone_setpoint(self, base_id: int, zone_id: int, setpoint: float) -> None:
        """Set zone setpoint temperature."""
        response = await self.http.post(
            f"/zones/{base_id}/{zone_id}",
            {"setpoint": setpoint}
        )
        if response.get("status") != 202:
            raise CommandFailedError(f"Failed to set zone setpoint to {setpoint}")
        # Invalidate zone cache after change
        self._cache.invalidate(f"zone_{base_id}_{zone_id}")

    async def set_zone_state(self, base_id: int, zone_id: int, state: int) -> None:
        """Set zone state."""
        response = await self.http.post(
            f"/zones/{base_id}/{zone_id}",
            {"state": state}
        )
        if response.get("status") != 202:
            raise CommandFailedError(f"Failed to set zone state to {state}")
        # Invalidate zone cache after change
        self._cache.invalidate(f"zone_{base_id}_{zone_id}")

    async def get_mixed_group_data(self, mixg_id: int) -> Dict[str, Any]:
        """Get mixed group data."""
        cache_key = f"mixedgroup_{mixg_id}"
        
        async def fetch():
            return await self.http.get(f"/mixedgroups/{mixg_id}")
        
        return await self._cache.get_or_fetch(cache_key, fetch)

    async def get_dehumidifier_state(self, dehumidifier_id: int) -> int:
        """Get dehumidifier state."""
        cache_key = f"dehumidifier_{dehumidifier_id}"
        
        async def fetch():
            data = await self.http.get(f"/dehumidifiers/{dehumidifier_id}")
            state = data.get("dehumidifier_state")
            if state is None:
                raise DataValidationError("Missing dehumidifier_state in response")
            return int(state)
        
        return await self._cache.get_or_fetch(cache_key, fetch)

    async def get_pump_state(self, pump_id: int) -> int:
        """Get pump state."""
        cache_key = f"pump_{pump_id}"
        
        async def fetch():
            data = await self.http.get(f"/pumps/{pump_id}")
            state = data.get("pump_state")
            if state is None:
                raise DataValidationError("Missing pump_state in response")
            return int(state)
        
        return await self._cache.get_or_fetch(cache_key, fetch)
    
    def invalidate_cache(self, key: Optional[str] = None) -> None:
        """Invalidate cache entries."""
        self._cache.invalidate(key) 