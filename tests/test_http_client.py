"""Tests for HTTP client module."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from aiohttp import ClientError

from custom_components.rehau_neasmart2.http_client import HttpClient, RehauNeasmart2ApiClient
from custom_components.rehau_neasmart2.exceptions import ConnectionError, DataValidationError, CommandFailedError


@pytest.fixture
async def http_client():
    """Create HTTP client instance."""
    client = HttpClient("http://test.local")
    yield client
    await client.close()


@pytest.fixture
async def api_client(http_client):
    """Create API client instance."""
    return RehauNeasmart2ApiClient(http_client)


class TestHttpClient:
    """Test HTTP client functionality."""

    async def test_connect(self, http_client):
        """Test connection creation."""
        await http_client.connect()
        assert http_client._session is not None

    async def test_health_check_success(self, http_client):
        """Test successful health check."""
        with patch.object(http_client, 'get', return_value={"status": 200}):
            result = await http_client.health_check()
            assert result is True

    async def test_health_check_failure(self, http_client):
        """Test failed health check."""
        with patch.object(http_client, 'get', side_effect=ConnectionError("test")):
            result = await http_client.health_check()
            assert result is False

    async def test_retry_logic(self, http_client):
        """Test retry logic on connection errors."""
        mock_session = MagicMock()
        mock_response = AsyncMock()
        
        # First two attempts fail, third succeeds
        side_effects = [
            ClientError("Connection failed"),
            ClientError("Connection failed"),
            mock_response
        ]
        
        mock_session.request = AsyncMock(side_effect=side_effects)
        mock_response.raise_for_status = MagicMock()
        mock_response.content_type = 'application/json'
        mock_response.json = AsyncMock(return_value={"test": "data"})
        
        http_client._session = mock_session
        
        result = await http_client.get("/test")
        assert result == {"test": "data"}
        assert mock_session.request.call_count == 3

    async def test_max_retries_exceeded(self, http_client):
        """Test that ConnectionError is raised after max retries."""
        mock_session = MagicMock()
        mock_session.request = AsyncMock(side_effect=ClientError("Connection failed"))
        http_client._session = mock_session
        
        with pytest.raises(ConnectionError) as exc:
            await http_client.get("/test")
        
        assert "Failed to connect" in str(exc.value)
        assert mock_session.request.call_count == 3  # MAX_RETRIES


class TestRehauNeasmart2ApiClient:
    """Test API client functionality."""

    async def test_get_outside_temperature_success(self, api_client):
        """Test successful outside temperature retrieval."""
        mock_data = {"outside_temperature": 15.5}
        with patch.object(api_client.http, 'get', return_value=mock_data):
            temp = await api_client.get_outside_temperature()
            assert temp == 15.5

    async def test_get_outside_temperature_missing_data(self, api_client):
        """Test error handling for missing temperature data."""
        mock_data = {}
        with patch.object(api_client.http, 'get', return_value=mock_data):
            with pytest.raises(DataValidationError) as exc:
                await api_client.get_outside_temperature()
            assert "Missing outside_temperature" in str(exc.value)

    async def test_get_outside_temperature_invalid_data(self, api_client):
        """Test error handling for invalid temperature data."""
        mock_data = {"outside_temperature": "invalid"}
        with patch.object(api_client.http, 'get', return_value=mock_data):
            with pytest.raises(DataValidationError) as exc:
                await api_client.get_outside_temperature()
            assert "Invalid temperature value" in str(exc.value)

    async def test_set_zone_state_success(self, api_client):
        """Test successful zone state update."""
        mock_response = {"status": 202}
        with patch.object(api_client.http, 'post', return_value=mock_response):
            # Should not raise
            await api_client.set_zone_state(1, 2, 3)

    async def test_set_zone_state_failure(self, api_client):
        """Test failed zone state update."""
        mock_response = {"status": 400}
        with patch.object(api_client.http, 'post', return_value=mock_response):
            with pytest.raises(CommandFailedError) as exc:
                await api_client.set_zone_state(1, 2, 3)
            assert "Failed to set zone state" in str(exc.value)

    async def test_cache_functionality(self, api_client):
        """Test that cache prevents duplicate API calls."""
        mock_data = {"outside_temperature": 20.0}
        with patch.object(api_client.http, 'get', return_value=mock_data) as mock_get:
            # First call should hit the API
            temp1 = await api_client.get_outside_temperature()
            assert temp1 == 20.0
            assert mock_get.call_count == 1
            
            # Second call should use cache
            temp2 = await api_client.get_outside_temperature()
            assert temp2 == 20.0
            assert mock_get.call_count == 1  # No additional API call

    async def test_cache_invalidation(self, api_client):
        """Test cache invalidation after state change."""
        mock_get_data = {"state": 1}
        mock_post_response = {"status": 202}
        
        with patch.object(api_client.http, 'get', return_value=mock_get_data) as mock_get:
            with patch.object(api_client.http, 'post', return_value=mock_post_response):
                # Get initial state (cached)
                state1 = await api_client.get_global_state()
                assert state1 == 1
                assert mock_get.call_count == 1
                
                # Set new state (should invalidate cache)
                await api_client.set_global_state(2)
                
                # Get state again (should hit API due to cache invalidation)
                state2 = await api_client.get_global_state()
                assert state2 == 1  # Still returns mock data
                assert mock_get.call_count == 2  # Additional API call

    async def test_get_zone_data_validation(self, api_client):
        """Test zone data validation."""
        # Missing required field
        mock_data = {
            "state": 1,
            "temperature": 20.0,
            "setpoint": 21.0
            # Missing "relative_humidity"
        }
        
        with patch.object(api_client.http, 'get', return_value=mock_data):
            with pytest.raises(DataValidationError) as exc:
                await api_client.get_zone_data(1, 1)
            assert "Missing required field" in str(exc.value)
            assert "relative_humidity" in str(exc.value) 