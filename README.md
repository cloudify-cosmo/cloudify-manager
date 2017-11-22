# Cloudify Manager Install
[![Circle CI](https://circleci.com/gh/cloudify-cosmo/cloudify-manager-install/tree/master.svg?style=shield)](https://circleci.com/gh/cloudify-cosmo/cloudify-manager-install/tree/master)
[![Code Health](https://landscape.io/github/cloudify-cosmo/cloudify-manager-install/master/landscape.svg?style=flat)](https://landscape.io/github/cloudify-cosmo/cloudify-manager-install/master)

A new, simpler, way to install a Cloudify manager.
Runs in half the time, with a fraction of the frustration.
1000% satisfaction guaranteed.

## Usage
### Installation

In the local install, the only thing the user needs, is a single RPM.

The RPM is now live on S3 (community version can be found [here](https://github.com/cloudify-cosmo/cloudify-versions/blob/master/packages-urls/manager-install-rpm.yaml), the
premium can be found [here](https://github.com/cloudify-cosmo/cloudify-premium/blob/master/packages-urls/manager-install-rpm.yaml)).
You can download and install it, following the instructions below.

For those who wish to manually create their own RPM (for development purposes)
see below steps 1-6.

#### Creating the RPM

1. SSH into a clean VM (or a bare metal server, of course).
2. Download the [`create_rpm.sh`](packaging/create_rpm.sh) script to the machine
with:

`curl -L -O https://raw.githubusercontent.com/cloudify-cosmo/cloudify-manager-install/master/packaging/create_rpm.sh`

3. Give it executable permissions:

`chmod +x create_rpm.sh`

4. The script requires a URL for the manager's resources archive
([community version](https://github.com/cloudify-cosmo/cloudify-versions/blob/master/packages-urls/manager-single-tar.yaml),
[premium version](https://github.com/cloudify-cosmo/cloudify-premium/blob/master/packages-urls/manager-single-tar.yaml)).
Pick the relevant link, and copy it.

5. Execute the script:

`./create_rpm.sh <RESOURCE_ARCHIVE_URL>`

6. This will result in an rpm created in `/tmp/cloudify-manager-install-1.0-1.x86_64.rpm`.

> Note that steps 1-6 may be performed on a machine other than the one
intended to serve as a Cloudify manager. It will be then up to the user
to ensure the `rpm` is then copied to the other machine.

#### Installing Cloudify Manager

7. `yum` install the rpm:

`sudo yum install -y /tmp/cloudify-manager-install-1.0-1.x86_64.rpm`

8. This step extracts necessary files on the system and gives permissions to the
`/opt/cloudify-manager-install` folder. One of the files extracted is the
`cfy_manager` executable which will be used to actually install the manager.
9. Only the private and public IPs are necessary to install the manager,
and those can be provided directly to the executable like this:

`cfy_manager install --private-ip <PRIVATE-IP> --public-ip <PUBLIC-IP>`

If more configurations are necessary, you may edit the config file in:
`/opt/cloudify-manager-install/config.yaml`. Any other values you might
wish to edit (beside the IPs) are set in [defaults.yaml](defaults.yaml).
The format of the file is basic YAML format.

10. After the command has finished, you should have a working manager,
with `cfy` installed for both the current user and `root`.

### Configuration
If you wish to change some configuration after install, just edit
`config.yaml` again and run `cfy_manager configure`. It takes about a minute.
As stated above, all the available configurations can be found in
[defaults.yaml](defaults.yaml).


### Teardown
At any point, you can run `cfy_manager remove`, which will remove everything
Cloudify related from the machine, except the installation code, that
will remain in `/opt/cloudify-manager-install/config.yaml`, so that you will
have the ability to run `cfy_manager install` again.


## Goodies
* `cfy_manager install` and `cfy_manager configure` can be run as many times as
you like. The commands are completely idempotent.
* Want to reconfigure the manager, but don't want to drop the DB?
Set `"postgres": {"create_db": false}"` in the config file.
* Working in offline mode? No problem. `cfy_manager install` can be used as is,
assuming the RPM was somehow delivered to the machine.
* Detailed debug logs of the installation process are available in
`/var/log/cloudify/manager/cfy_manager.log`
