"""Custom exceptions for Rehau Neasmart 2.0 integration."""


class RehauNeasmart2Error(Exception):
    """Base exception for Rehau Neasmart 2.0 integration."""
    pass


class ConnectionError(RehauNeasmart2Error):
    """Exception raised when unable to connect to the shim server."""
    pass


class AuthenticationError(RehauNeasmart2Error):
    """Exception raised when authentication fails."""
    pass


class DataValidationError(RehauNeasmart2Error):
    """Exception raised when received data is invalid."""
    pass


class DeviceNotFoundError(RehauNeasmart2Error):
    """Exception raised when a device is not found."""
    pass


class CommandFailedError(RehauNeasmart2Error):
    """Exception raised when a command to the device fails."""
    pass


class ConfigurationError(RehauNeasmart2Error):
    """Exception raised for configuration-related errors."""
    pass 