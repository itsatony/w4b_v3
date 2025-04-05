"""Compose configuration module."""
class ComposeConfig:
    """Handles compose file parsing and validation."""
    def __init__(self):
        self.groups = {}
        self.services = {}
