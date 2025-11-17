# Rehau Neasmart 2.0 Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)]()

This custom component allows you to integrate your Rehau Neasmart 2.0 climate control system with Home Assistant through the REST API gateway.

## Overview

The Rehau Neasmart 2.0 integration provides full control over your heating/cooling zones through Home Assistant. It communicates with your Neasmart system via a REST API gateway, allowing you to monitor and control temperature, humidity, and operation states for each zone.

## Features

- **Zone Control**: Monitor and control individual heating/cooling zones
- **Temperature Management**: View current temperature and adjust setpoints
- **Humidity Monitoring**: Track relative humidity in each zone
- **Operation States**: Switch between different operation modes (Normal, Reduced, Standby, Scheduled, Party, Holiday)
- **Global Control**: Set system-wide operation state
- **Real-time Updates**: Automatic synchronization with your Neasmart system
- **Multi-language Support**: Available in English and Italian

## Requirements

- Home Assistant 2023.1 or newer
- Rehau Neasmart 2.0 system
- REST API gateway for Neasmart (with API v2.1.0 or newer)
- Network connectivity between Home Assistant and the API gateway

## Installation

### HACS Installation (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots menu in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/yourusername/rehau-neasmart2.0-integration-ha`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Rehau Neasmart 2.0"
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Copy the `custom_components/rehau_neasmart2` folder to your Home Assistant's `custom_components` directory
2. Restart Home Assistant

## Configuration

The integration uses a multi-step configuration wizard to guide you through the setup process:

### Step 1: API Connection

Enter the connection details for your Neasmart API gateway:

- **API Server Address**: IP address or hostname (e.g., 192.168.1.100)
- **API Server Port**: Port number (default: 80)

### Step 2: System Name

Choose a display name for your climate control system. This name will be used to identify your system in Home Assistant.

### Step 3: Zone Configuration

The integration will automatically detect all available zones from your Neasmart system. You can customize the display name for each zone to match your preferences (e.g., "Living Room", "Bedroom", "Kitchen").

## Entities

The integration creates the following entities for each configured zone:

### Climate Entities

- **Zone Thermostats**: Control temperature and operation mode for each zone
  - Current temperature display
  - Target temperature adjustment (5°C - 30°C)
  - Preset mode selection
  - Humidity display

### Select Entities

- **Global Operation State**: Control the system-wide operation mode

### Sensor Entities

- **Temperature Sensors**: Current temperature for each zone
- **Humidity Sensors**: Current relative humidity for each zone
- **Setpoint Sensors**: Current target temperature for each zone

## Operation States

The system supports the following operation states:

- **Normal**: Standard operation mode
- **Reduced**: Energy-saving mode with reduced temperature
- **Standby**: Minimal operation mode
- **Scheduled**: Follow programmed schedule
- **Party**: Temporary comfort mode
- **Holiday**: Extended absence mode

## Troubleshooting

### Connection Issues

If you're experiencing connection problems:

1. Verify the API gateway is running and accessible
2. Check the IP address and port are correct
3. Ensure there's no firewall blocking the connection
4. Test the API directly using: `curl http://YOUR_IP:PORT/api/health`

### Zone Detection Issues

If zones are not detected:

1. Verify the API gateway has access to the Modbus network
2. Check that zones are properly configured in the Neasmart system
3. Review the Home Assistant logs for error messages

### Update Issues

If entities are not updating:

1. Check the Home Assistant logs for errors
2. Verify the API gateway is responding
3. Try reloading the integration
4. Consider increasing the update interval if the system is overloaded

## API Documentation

This integration uses the Rehau Neasmart 2.0 REST API v2.1.0. The API specification is available in the `openapi.yaml` file.

Key endpoints used:

- `GET /api/zones` - List all zones
- `GET /api/zones/{base_id}/{zone_id}` - Get zone details
- `POST /api/zones/{base_id}/{zone_id}` - Update zone settings
- `GET /api/operation/state` - Get global operation state
- `POST /api/operation/state` - Set global operation state
- `GET /api/health` - System health check

## Migration from Old Version

If you're upgrading from an older version of the integration, the configuration will be automatically migrated to the new format. The migration process:

1. Converts comma-separated zone lists to structured zone configurations
2. Maps old server host/port to new API URL format
3. Preserves zone names and system configuration

## Development

### Project Structure

```
custom_components/rehau_neasmart2/
├── __init__.py          # Integration setup and initialization
├── climate.py           # Climate platform implementation
├── config_flow.py       # Configuration flow handlers
├── const.py            # Constants and configuration
├── exceptions.py       # Custom exception classes
├── http_client.py      # API client implementation
├── hub.py              # Central hub/coordinator
├── models.py           # Data models and structures
├── select.py           # Select platform implementation
├── sensor.py           # Sensor platform implementation
├── manifest.json       # Integration manifest
├── strings.json        # Default strings
└── translations/       # Localization files
    ├── en.json        # English translations
    └── it.json        # Italian translations
```

### Future Enhancements

The following features are planned for future releases when API support becomes available:

- Mixed group monitoring and control
- Pump status and control
- Dehumidifier integration
- Advanced scheduling
- Energy consumption tracking
- Historical data analysis

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add/update tests as needed
5. Submit a pull request

## Support

For issues and feature requests, please use the [GitHub issue tracker](https://github.com/giacomoalonzi/rehau-neasmart2.0-integration-ha/issues).

For general questions about the Rehau Neasmart 2.0 system, consult the official Rehau documentation.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to the Home Assistant community for the excellent development platform
- Thanks to Rehau for the Neasmart 2.0 climate control system
- Thanks to all contributors and testers

---

**Note**: This integration is not officially affiliated with or endorsed by Rehau. Use at your own risk.
