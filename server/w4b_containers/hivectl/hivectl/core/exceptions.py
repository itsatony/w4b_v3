"""Custom exceptions for HiveCtl."""
class HiveCtlError(Exception):
    """Base exception for all HiveCtl errors."""
    pass
    
class ComposeFileNotFound(HiveCtlError):
    """Exception raised when compose file is not found."""
    def __init__(self, message="Compose file not found in current directory"):
        self.message = message
        super().__init__(self.message)
