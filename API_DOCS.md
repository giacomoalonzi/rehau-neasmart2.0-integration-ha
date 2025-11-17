# Rehau Neasmart 2.0 API Documentation

## API Endpoints

The Rehau Neasmart 2.0 REST API provides endpoints for controlling and monitoring your climate control system.

### Base URLs

- **Local**: http://localhost:5001
- **Docker**: http://<container-ip>:5001
- **Production**: https://your-production-domain.com

## Endpoints

### Health Check

Get system health status.

**Endpoint**: `GET /api/health`

**Response**: System health information including database and Modbus connectivity status.

### Zones

List all configured zones.

**Endpoint**: `GET /api/zones`

**Response**: Array of zone objects with current state, temperature, and setpoint information.

### Zone Details

Get specific zone information.

**Endpoint**: `GET /api/zones/{base_id}/{zone_id}`

**Parameters**:
- `base_id` (integer, 1-4): Base station ID
- `zone_id` (integer, 1-12): Zone ID within the base

**Response**: Detailed zone information including state, temperature, humidity, and setpoint.

### Update Zone

Update zone state or setpoint.

**Endpoint**: `POST /api/zones/{base_id}/{zone_id}`

**Request Body**:
```json
{
  "state": "presence",
  "setpoint": 22.5
}
```

### Operation State

Get or set global operation state.

**Endpoints**:
- `GET /api/state` - Get current operation state
- `POST /api/state` - Set operation state

**Request Body** (POST):
```json
{
  "state": "presence"
}
```

## Authentication

The API may require authentication depending on your gateway configuration. Check your gateway settings for API authentication requirements.

## Error Handling

The API returns standard HTTP status codes:
- `200` - Success
- `400` - Bad Request (validation error)
- `503` - Service Unavailable (Modbus communication error)

## OpenAPI Specification

A complete OpenAPI 3.0 specification is available in `openapi.yaml` for detailed endpoint documentation and request/response schemas.

