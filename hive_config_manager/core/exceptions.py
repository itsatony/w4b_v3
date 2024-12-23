# hive_config_manager/core/exceptions.py

class HiveConfigError(Exception):
    """Base exception for hive configuration errors"""
    pass

class ValidationError(HiveConfigError):
    """Raised when configuration validation fails"""
    def __init__(self, errors: list):
        self.errors = errors
        super().__init__("\n".join(errors))

class ConfigNotFoundError(HiveConfigError):
    """Raised when a hive configuration file is not found"""
    def __init__(self, hive_id: str):
        self.hive_id = hive_id
        super().__init__(f"Configuration not found for hive: {hive_id}")

class ConfigAccessError(HiveConfigError):
    """Raised when there are permission or I/O errors with config files"""
    pass

class DuplicateHiveError(HiveConfigError):
    """Raised when attempting to create a hive with an existing ID"""
    def __init__(self, hive_id: str):
        self.hive_id = hive_id
        super().__init__(f"Hive already exists: {hive_id}")

class InvalidOperationError(HiveConfigError):
    """Raised when attempting an invalid operation"""
    pass

class BackupError(HiveConfigError):
    """Raised when backup creation fails"""
    pass

class NetworkConfigError(ValidationError):
    """Raised for network configuration specific errors"""
    pass

class SensorConfigError(ValidationError):
    """Raised for sensor configuration specific errors"""
    pass

class AdministratorConfigError(ValidationError):
    """Raised for administrator configuration specific errors"""
    pass

class MaintenanceConfigError(ValidationError):
    """Raised for maintenance configuration specific errors"""
    pass

class FileSystemError(HiveConfigError):
    """Raised for file system related errors"""
    pass

class ConfigVersionError(HiveConfigError):
    """Raised when configuration version is incompatible"""
    def __init__(self, current_version: str, required_version: str):
        self.current_version = current_version
        self.required_version = required_version
        super().__init__(
            f"Configuration version mismatch: "
            f"got {current_version}, requires {required_version}"
        )

class LockError(HiveConfigError):
    """Raised when unable to acquire lock for configuration changes"""
    def __init__(self, hive_id: str):
        self.hive_id = hive_id
        super().__init__(
            f"Unable to acquire lock for hive: {hive_id}. "
            "Another process may be modifying the configuration."
        )

class ValidationWarning(Warning):
    """Warning for non-critical validation issues"""
    pass

def handle_config_error(error: HiveConfigError) -> str:
    """
    Convert a configuration error to a user-friendly message.
    
    Args:
        error: The error to handle
        
    Returns:
        A formatted error message
    """
    if isinstance(error, ValidationError):
        return "Validation errors:\n" + "\n".join(f"  • {e}" for e in error.errors)
    elif isinstance(error, ConfigNotFoundError):
        return f"Configuration not found: {error.hive_id}"
    elif isinstance(error, DuplicateHiveError):
        return f"Hive already exists: {error.hive_id}"
    elif isinstance(error, ConfigVersionError):
        return (f"Configuration version mismatch:\n"
                f"  Current: {error.current_version}\n"
                f"  Required: {error.required_version}")
    elif isinstance(error, LockError):
        return (f"Cannot modify configuration for {error.hive_id}:\n"
                "Another process is currently making changes.")
    else:
        return str(error)