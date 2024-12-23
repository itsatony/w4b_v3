# hive_config_manager/cli/interface.py

import os
import sys
from typing import Optional
from prompt_toolkit import Application
from prompt_toolkit.layout.containers import HSplit, VSplit, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import Frame, TextArea, Label
import yaml

from ..core.manager import HiveManager
from ..core.exceptions import HiveConfigError
from .prompts import HivePrompts

from ..core.exceptions import (
    HiveConfigError, ValidationError, ConfigNotFoundError,
    DuplicateHiveError, LockError, handle_config_error
)

class HiveManagerCLI:
    """
    Interactive CLI interface for the Hive Configuration Manager.
    
    Features:
    - List/view/edit/delete hive configurations
    - Keyboard shortcuts for common operations
    - Live validation feedback
    - Configuration syntax highlighting
    """

    def __init__(self):
        self.manager = HiveManager()
        self.prompts = HivePrompts()
        self.current_hive: Optional[str] = None
        self.kb = KeyBindings()
        self.setup_keybindings()
        
        # UI components
        self.hive_list = TextArea(
            focusable=True,
            read_only=True,
            scrollbar=True,
            height=10
        )
        
        self.status_bar = FormattedTextControl("")
        self.command_bar = FormattedTextControl(
            "[n]ew [e]dit [d]elete [v]alidate [q]uit"
        )
        
        self.editor = TextArea(
            focusable=True,
            scrollbar=True,
            height=20
        )
        
        self.layout = self.create_layout()
        self.style = self.create_style()
        
        self.app = Application(
            layout=self.layout,
            key_bindings=self.kb,
            style=self.style,
            full_screen=True,
            mouse_support=True
        )

    def setup_keybindings(self):
        """Setup keyboard shortcuts"""
        
        @self.kb.add('c-c', eager=True)
        @self.kb.add('c-q')
        def _(event):
            """Quit the application"""
            event.app.exit()
        
        @self.kb.add('n')
        def _(event):
            """Create new hive"""
            self.create_new_hive()
        
        @self.kb.add('e')
        def _(event):
            """Edit selected hive"""
            if self.current_hive:
                self.edit_hive(self.current_hive)
        
        @self.kb.add('d')
        def _(event):
            """Delete selected hive"""
            if self.current_hive:
                self.delete_hive(self.current_hive)
        
        @self.kb.add('v')
        def _(event):
            """Validate selected hive"""
            if self.current_hive:
                self.validate_hive(self.current_hive)
        
        @self.kb.add('tab')
        def _(event):
            """Switch focus between panels"""
            if event.app.layout.current_window == self.hive_list:
                event.app.layout.focus(self.editor)
            else:
                event.app.layout.focus(self.hive_list)

    def create_layout(self):
        """Create the application layout"""
        return Layout(
            HSplit([
                VSplit([
                    Frame(
                        title="Hives",
                        body=self.hive_list
                    ),
                    Frame(
                        title="Editor",
                        body=self.editor
                    )
                ]),
                Frame(
                    title="Status",
                    body=Window(self.status_bar),
                    height=3
                ),
                Window(
                    content=self.command_bar,
                    height=1,
                    style="class:command-bar"
                )
            ])
        )

    def create_style(self):
        """Create the application style"""
        return Style.from_dict({
            'frame.border': '#888888',
            'frame.title': 'bold #ffffff',
            'status-bar': 'reverse',
            'command-bar': 'reverse',
            'error': '#ff0000',
            'success': '#00ff00'
        })

    def update_hive_list(self):
        """Update the list of hives"""
        hives = self.manager.list_hives()
        text = "\n".join(
            f"{'> ' if h == self.current_hive else '  '}{h}"
            for h in hives
        )
        self.hive_list.text = text

    def set_status(self, message: str, style: str = ""):
        """Update the status bar"""
        self.status_bar.text = [(style, message)]

    def create_new_hive(self):
        """Create a new hive configuration with error handling"""
        try:
            config = self.prompts.get_new_hive_config()
            hive_id = self.manager.create_hive(config)
            self.current_hive = hive_id
            self.update_hive_list()
            self.set_status(f"Created hive {hive_id}", "class:success")
        except ValidationError as e:
            self.set_status("Validation errors:\n" + "\n".join(e.errors), "class:error")
        except DuplicateHiveError as e:
            self.set_status(str(e), "class:error")
        except LockError as e:
            self.set_status(str(e), "class:error")
        except HiveConfigError as e:
            self.set_status(handle_config_error(e), "class:error")
        except Exception as e:
            self.set_status(f"Unexpected error: {str(e)}", "class:error")

    def edit_hive(self, hive_id: str):
        """Edit a hive configuration with error handling"""
        try:
            config = self.manager.get_hive(hive_id)
            self.editor.text = self.prompts.format_config(config)
            self.set_status(f"Editing {hive_id}")
            
            # Handle configuration updates
            updated_config = yaml.safe_load(self.editor.text)
            self.manager.update_hive(hive_id, updated_config)
            self.set_status(f"Updated {hive_id}", "class:success")
        except ValidationError as e:
            self.set_status("Validation errors:\n" + "\n".join(e.errors), "class:error")
        except ConfigNotFoundError as e:
            self.set_status(str(e), "class:error")
        except LockError as e:
            self.set_status(str(e), "class:error")
        except yaml.YAMLError as e:
            self.set_status(f"Invalid YAML format: {str(e)}", "class:error")
        except HiveConfigError as e:
            self.set_status(handle_config_error(e), "class:error")
        except Exception as e:
            self.set_status(f"Unexpected error: {str(e)}", "class:error")

    def delete_hive(self, hive_id: str):
        """Delete a hive configuration"""
        try:
            if self.prompts.confirm_deletion(hive_id):
                self.manager.delete_hive(hive_id)
                self.current_hive = None
                self.update_hive_list()
                self.set_status(f"Deleted hive {hive_id}", "class:success")
        except Exception as e:
            self.set_status(f"Error: {str(e)}", "class:error")

    def validate_hive(self, hive_id: str):
        """Validate a hive configuration with detailed feedback"""
        try:
            errors = self.manager.validate_hive(hive_id)
            if errors:
                formatted_errors = "\n".join(f"• {error}" for error in errors)
                self.set_status(
                    "Validation errors:\n" + formatted_errors,
                    "class:error"
                )
            else:
                self.set_status("Configuration is valid", "class:success")
        except ConfigNotFoundError as e:
            self.set_status(str(e), "class:error")
        except HiveConfigError as e:
            self.set_status(handle_config_error(e), "class:error")
        except Exception as e:
            self.set_status(f"Unexpected error: {str(e)}", "class:error")

    def run(self):
        """Run the CLI interface"""
        self.update_hive_list()
        self.app.run()