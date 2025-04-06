# Tasks and Progress tracking for the w4b raspi image generator

## Tasks

### Core Framework

- [x] DONE: Design declarative configuration schema
  - [x] Define YAML structure for image configurations
  - [x] Create environment variable mapping
  - [x] Implement configuration validation
  - [x] Support inheritance and overrides

- [x] DONE: Create base image acquisition module
  - [x] Implement base image download with checksum verification
  - [x] Add caching mechanism for efficiency
  - [x] Support multiple Raspberry Pi OS versions
  - [x] Support different Raspberry Pi hardware models

- [x] DONE: Implement disk image manipulation
  - [x] Create disk mounting and unmounting utilities
  - [x] Implement filesystem modification capabilities
  - [x] Add partition management utilities
  - [x] Create file injection mechanisms

- [x] DONE: Develop system configuration module
  - [x] Implement hostname and network configuration
  - [x] Add locale and timezone settings
  - [x] Create user management utilities
  - [x] Implement boot configuration

- [x] DONE: Create security configuration module
  - [x] Implement SSH key setup and configuration
  - [x] Add WireGuard VPN configuration 
  - [x] Create firewall rule management
  - [x] Implement security hardening

- [x] DONE: Implement software installation module
  - [x] Create package installation mechanism
  - [x] Create service configuration utilities
  - [x] Shift to firstboot script approach
  - [x] Implement bootup triggered auto-installation

- [ ] TODO: Create documentation
  - [ ] Update README with new approach
  - [ ] Document configuration options
  - [ ] Create usage examples
  - [ ] Document troubleshooting steps

- [ ] TODO: Create testing framework
  - [ ] Implement automated image verification
  - [ ] Create integration tests
  - [ ] Setup CI/CD pipeline

## Architecture Decision Records (ADRs)

### ADR: Switch from QEMU-based modification to firstboot script approach

- Context: We encountered persistent issues with QEMU-based ARM emulation for modifying Raspberry Pi images. The approach was unreliable across different host systems and frequently failed with "No such file or directory" errors when attempting to use qemu-arm-static in chroot environments.
- Decision: We will switch to a firstboot script approach where we prepare the image with scripts that run automatically when the Raspberry Pi boots for the first time. This will handle package installation, service configuration, and system setup.
- Consequences: 
  - More reliable image generation as we no longer depend on QEMU emulation working correctly
  - First boot will take longer as packages are installed at that time rather than during image creation
  - Images will be smaller initially but require internet connectivity during first boot
  - Better compatibility across different Raspberry Pi models as the setup happens natively on the target hardware

### ADR: Use TimescaleDB for time-series data storage

- Context: We need a database for storing time-series data from the sensors.
- Decision: We will use TimescaleDB as our time-series database.
- Consequences: We will need to set up TimescaleDB on the server and configure it for use with our API service.

### ADR: Implement multi-stage image preparation process

- Context: Image generation involves several distinct stages that can fail independently.
- Decision: We will implement a pipeline approach with discrete stages (download, mount, system config, software install, etc.) that can be run and debugged independently.
- Consequences: Better error handling, more maintainable code, ability to resume from failures, and clearer logging and diagnostics.

