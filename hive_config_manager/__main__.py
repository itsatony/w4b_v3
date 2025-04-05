# hive_config_manager/__main__.py

import sys
import argparse
from pathlib import Path

try:
    # When running as a package
    from .cli.interface import HiveManagerCLI
    from .core.manager import HiveManager
    from .core.exceptions import HiveConfigError
except ImportError:
    # When running the file directly
    from cli.interface import HiveManagerCLI
    from core.manager import HiveManager
    from core.exceptions import HiveConfigError

def main():
    """Main entry point for the Hive Configuration Manager"""
    parser = argparse.ArgumentParser(
        description="Manage hive configurations"
    )
    parser.add_argument(
        '--path',
        type=Path,
        help='Path to hives directory'
    )
    parser.add_argument(
        '--validate',
        metavar='HIVE_ID',
        help='Validate specific hive configuration'
    )
    
    args = parser.parse_args()
    
    try:
        if args.validate:
            # Run validation only
            manager = HiveManager(args.path)
            errors = manager.validate_hive(args.validate)
            if errors:
                print("Validation errors:")
                for error in errors:
                    print(f"  • {error}")
                sys.exit(1)
            else:
                print("Configuration is valid")
                sys.exit(0)
        else:
            # Start interactive CLI
            cli = HiveManagerCLI()
            cli.run()
    except HiveConfigError as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

if __name__ == "__main__":
    main()