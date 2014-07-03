Window Agent Installer
======================

This is a Cloudify plugin for installing cloudify agents on Windows machines.

## Pre-requisites

To use this plugin, WinRM must be properly setup on the destination machine.

      winrm quickconfig
      winrm s winrm/config/service @{AllowUnencrypted="true";MaxConcurrentOperationsPerUser="4294967295"}
      winrm s winrm/config/service/auth @{Basic="true"}
      winrm s winrm/config/winrs @{MaxShellsPerUser="2147483647"}

In addition, Python 2.7 must be installed on the machine.

**API**

- tasks.install: Downloads the agent package do the destination machine and extracts it.
- tasks.start: Starts the agent as a Windows service.
- tasks.stop: Stops the service.
- tasks.restart: Restarts the service.
- tasks.uninstall: Removes the service and any files from the file system.

**Additional Configuration**

This plugin allows for specific windows service configuration parameters as part of the 'cloudify_agent' dictionary.
These parameters will be passed to the CloudifyAgent service on the machine.

NOTE : The values stated here are just the default values, you can override them by passing your own 'cloudify_agent'
 dictionary

      'service':
         'start_timeout': 30,
         'stop_timeout': 30,
         'status_transition_sleep_interval': 5,
         'successful_consecutive_status_queries_count': 3,
         'failure_reset_timeout': 60,
         'failure_restart_delay': 5000
      }

**Example Usage**

See [Tests](https://github.com/cloudify-cosmo/cloudify-manager/plugins/windows_agent_installer/windows_agent_installer/tests/test_tasks.py)


