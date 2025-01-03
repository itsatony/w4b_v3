"""
Custom exceptions for the HiveCtl application.
"""

class HiveCtlError(Exception):
    """Base exception for HiveCtl errors."""
    pass

class ComposeError(HiveCtlError):
    """Raised when there are issues with the compose file."""
    pass

class ComposeFileNotFound(ComposeError):
    """Raised when the compose file is not found in the current directory."""
    def __init__(self, message="No compose.yaml file found in current directory"):
        self.message = message
        super().__init__(self.message)

class InvalidComposeFile(ComposeError):
    """Raised when the compose file is invalid or missing required labels."""
    pass

class ContainerError(HiveCtlError):
    """Raised for container-related errors."""
    pass

class ContainerNotFound(ContainerError):
    """Raised when a specified container is not found."""
    pass

class ContainerOperationError(ContainerError):
    """Raised when a container operation fails."""
    pass

class NetworkError(HiveCtlError):
    """Raised for network-related errors."""
    pass

class NetworkNotFound(NetworkError):
    """Raised when a specified network is not found."""
    pass

class NetworkOperationError(NetworkError):
    """Raised when a network operation fails."""
    pass

class VolumeError(HiveCtlError):
    """Raised for volume-related errors."""
    pass

class VolumeNotFound(VolumeError):
    """Raised when a specified volume is not found."""
    pass

class VolumeOperationError(VolumeError):
    """Raised when a volume operation fails."""
    pass

class ConfigurationError(HiveCtlError):
    """Raised for configuration-related errors."""
    pass

class MissingLabelsError(ConfigurationError):
    """Raised when required labels are missing in the compose file."""
    def __init__(self, service_name, missing_labels):
        self.service_name = service_name
        self.missing_labels = missing_labels
        message = f"Service '{service_name}' is missing required labels: {', '.join(missing_labels)}"
        super().__init__(message)

class DependencyError(HiveCtlError):
    """Raised for dependency-related errors."""
    pass

class CircularDependencyError(DependencyError):
    """Raised when circular dependencies are detected."""
    pass

class HealthCheckError(HiveCtlError):
    """Base class for health check related errors."""
    def __init__(self, service_name, message, recovery_suggestion=None):
        self.service_name = service_name
        self.recovery_suggestion = recovery_suggestion
        full_message = f"Health check failed for service '{service_name}': {message}"
        if recovery_suggestion:
            full_message += f"\nSuggested recovery: {recovery_suggestion}"
        super().__init__(full_message)

class HealthCheckTimeout(HealthCheckError):
    """Raised when a health check times out."""
    def __init__(self, service_name, timeout):
        super().__init__(
            service_name,
            f"Health check timed out after {timeout} seconds",
            "Try increasing the health check timeout or check service logs for delays"
        )

class ResourceWarning(Warning):
    """Base class for resource-related warnings."""
    def __init__(self, message, resource_type, current_value, threshold, suggestion=None):
        self.resource_type = resource_type
        self.current_value = current_value
        self.threshold = threshold
        self.suggestion = suggestion
        full_message = f"{message}\nCurrent {resource_type}: {current_value}\nThreshold: {threshold}"
        if suggestion:
            full_message += f"\nSuggestion: {suggestion}"
        super().__init__(full_message)

class MemoryWarning(ResourceWarning):
    """Warning for memory usage approaching limits."""
    def __init__(self, current_mb, limit_mb):
        super().__init__(
            "Memory usage high",
            "memory",
            f"{current_mb}MB",
            f"{limit_mb}MB",
            "Consider increasing container memory limit or optimizing application"
        )

class CPUWarning(ResourceWarning):
    """Warning for CPU usage approaching limits."""
    def __init__(self, current_percent, threshold_percent):
        super().__init__(
            "CPU usage high",
            "CPU",
            f"{current_percent}%",
            f"{threshold_percent}%",
            "Consider increasing CPU quota or investigating high CPU consumers"
        )

class DiskWarning(ResourceWarning):
    """Warning for disk usage approaching limits."""
    def __init__(self, current_gb, limit_gb):
        super().__init__(
            "Disk usage high",
            "disk",
            f"{current_gb}GB",
            f"{limit_gb}GB",
            "Consider cleaning up old data or increasing volume size"
        )

class CommandError(HiveCtlError):
    """Raised for command execution errors."""
    def __init__(self, command, error_message, return_code=None, recovery_suggestion=None):
        self.command = command
        self.error_message = error_message
        self.return_code = return_code
        self.recovery_suggestion = recovery_suggestion
        message = f"Command '{command}' failed with error: {error_message}"
        if return_code is not None:
            message += f" (return code: {return_code})"
        if recovery_suggestion:
            message += f"\nSuggested recovery: {recovery_suggestion}"
        super().__init__(message)