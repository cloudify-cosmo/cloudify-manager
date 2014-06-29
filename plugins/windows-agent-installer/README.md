Window Agent Installer
======================

This is a Cloudify plugin for installing cloudify agents on Windows machines.

## Pre-requisites

To use this plugin, WinRM must be properly setup on the destination machine.

      winrm quickconfig
      winrm s winrm/config/service @{AllowUnencrypted="true";MaxConcurrentOperationsPerUser="4294967295"}
      winrm s winrm/config/service/auth @{Basic="true"}
      winrm s winrm/config/winrs @{MaxShellsPerUser="2147483647"}

**API**

- tasks.install: Downloads the agent package do the destination machine and extracts it.
- tasks.start: Starts the agent as a Windows service.
- tasks.stop: Stops the service.
- tasks.restart: Restarts the service.
- tasks.uninstall: Removes the service and any files from the file system.

**Example Usage**

See [Tests](https://github.com/cloudify-cosmo/cloudify-manager/plugins/windows_agent_installer/windows_agent_installer/tests/test_tasks.py)
