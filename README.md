# Cloudify Local Bootstrap
[![Circle CI](https://circleci.com/gh/mcouthon/cloudify-local-bootstrap/tree/master.svg?style=shield)](https://circleci.com/gh/mcouthon/cloudify-local-bootstrap/tree/master)
[![Code Health](https://landscape.io/github/mcouthon/cloudify-local-bootstrap/master/landscape.svg?style=flat)](https://landscape.io/github/mcouthon/cloudify-local-bootstrap/master)

A new, simpler, way to bootstrap a Cloudify manager.
Runs in half the time, with a fraction of the frustration.
1000% satisfaction guaranteed.

## Usage
### Installation

In the local bootstrap, the only thing the user needs, is a single RPM.

It will, eventually, live somewhere on S3, and will be easily available
to all. For now though, it needs to be manually created (see below
steps 1-6).

#### Creating the RPM

1. SSH into a clean VM (or a bare metal server, of course).
2. Download the [`create_rpm.sh`](create_rpm.sh) script to the machine
with:

`curl -L https://raw.githubusercontent.com/mcouthon/cloudify-local-bootstrap/master/create_rpm.sh -o /tmp/create_rpm.sh `

3. Give it executable permissions:

`chmod +x /tmp/create_rpm.sh`

5. Execute it:

`/tmp/create_rpm.sh`

6. This will result in an rpm created in `/tmp/cloudify-bootstrap-1.0-1.x86_64.rpm` (version may vary).

> Note that steps 1-6 may be performed on a machine other than the one
intended to serve as a Cloudify manager. It will be then up to the user
to ensure the `rpm` is then copied to the other machine.

#### Installing Cloudify Manager

7. Install the rpm:

`sudo yum install -y /tmp/cloudify-bootstrap-1.0-1.x86_64.rpm`

8. This will put all the necessary files in `/opt/cloudify-bootstrap`.
9. Edit the config file in: `/opt/cloudify-bootstrap/config.json`. Only
the private and public IPs are required. Any other values you might
wish to edit are set in [defaults.json](defaults.json). The format of
the file is basic (strict) JSON format.
10. To install the manager, execute  `cfy_install`.
11. After the command has finished, you should have a working manager,
with `cfy` installed for both the current user and `root`.

### Configuration
If you wish to change some configuration after install, just edit
`config.json` again and run `cfy_config`. It takes about a minute.
As stated above, all the available configurations can be found in
[defaults.json](defaults.json).


### Teardown
At any point, you can run `cfy_remove`, which will remove everything
Cloudify related from the machine, except the installation code, that
will remain in `/opt/cloudify-bootstrap/config.json`, so that you will
have the ability to run `cfy_install` again.


## Goodies
* `cfy_install` and `cfy_config` can be run as many times as you like.
* Want to reconfigure the manager, but don't want to drop the DB?
Set `"postgres": {"create_db": false}"` in the config file.
* Working in offline mode? No problem. `cfy_install` can be used as is,
assuming the RPM was somehow delivered to the machine.
* Running bootstraps on multiple machines in parallel? It's easier than
ever. Because you no longer need a central CLI location, parallelization
is a breeze.
