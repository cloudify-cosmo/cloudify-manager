Window Agent Installer Tests
============================

The tests require a specific image that will server as the remote machine.

**Steps for creating an image**

Provision a windows machine in the cloud of your chioce and do the following:

1) Download and install Python 2.7 - [Get Python] (https://ninite.com/python/) <br>
2) Donwload and install Erlang Binaries - [Get Erlang] (http://www.erlang.org/download.html) <br>
3) Donwload and install RabbitMQ Server - [Get RabbitMQ] (http://www.erlang.org/download.html) <br>
4) Run the following commands:

      winrm quickconfig
      winrm s winrm/config/service @{AllowUnencrypted="true";MaxConcurrentOperationsPerUser="4294967295"}
      winrm s winrm/config/service/auth @{Basic="true"}
      winrm s winrm/config/winrs @{MaxShellsPerUser="2147483647"}
