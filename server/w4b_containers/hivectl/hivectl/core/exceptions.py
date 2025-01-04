"""
Custom exceptions for the HiveCtl application.
"""

class HiveCtlError(Exception):
    """Base exception for HiveCtl errors."""
    def __init__(self, message: str, recovery_suggestion: str = None):
        super().__init__(message)
        self.recovery_suggestion = recovery_suggestion

class ComposeError(HiveCtlError):
    """Raised when there are issues with the compose file."""
    pass

class ComposeFileNotFound(HiveCtlError):
    """Raised when compose file is not found."""
    def __init__(self):
        super().__init__(
            "No compose.yaml or compose.yml found in current directory",
            "Please run hivectl from a directory containing a compose file"
        )

class InvalidComposeFile(ComposeError):
    """Raised when the compose file is invalid or missing required labels."""
    pass

class ComposeParseError(HiveCtlError):
    """Raised when compose file cannot be parsed."""
    def __init__(self, detail: str):
        super().__init__(
            f"Failed to parse compose file: {detail}",
            "Please check your compose file syntax"
        )

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

class HealthCheckError(ContainerError):
    """Raised when a health check fails."""
    pass

class HealthCheckTimeout(HealthCheckError):
    """Raised when a health check times out."""
    pass

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
    """Raised when a command fails."""
    def __init__(self, cmd: str, error: str, code: int = None):
        msg = f"Command failed: {error}"
        if code:
            msg += f" (exit code {code})"
        super().__init__(msg, f"Command was: {cmd}")