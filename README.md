# cloudify-local-bootstrap
A new, simpler, way to bootstrap a Cloudify manager.
Runs in half the time, with a fraction of the frustration.
1000% satisfaction guaranteed.

## Usage
### Installation
1. Get a clean VM.
1. yum install the magic rpm (see [here](#creating-the-rpm)).
1. Edit `config.json` in `/opt/cloudify-bootstrap/config.json`
(only `private_ip` and `public_ip` params are required).
1. Run `cfy_install`.
1. Profit.

### Configuration
If you wish to change some configuration after install, just edit
`config.json` again and run `cfy_config`. It takes about a minute. Nice!
All the available configurations can be found in
[defaults.json](defaults.json).


### Teardown
Sick of cloudify? No problem, just run `cfy_remove`, and go to the
beach.

### Creating the RPM
Eventually the process will be fully automated, and the rpm will be
available publicly on S3, but for now, if you want to create a full
fledged cloudify manager rpm, just run the
[create_rpm.sh](create_rpm.sh) script.


## Goodies
* `cfy_install` and `cfy_config` can be run as many times as you like.
Give it a try!
* Cloudify CLI is already installed (for both root and the default
user!). Just like that. Because we like you.
* Want to reconfigure the manager, but don't want to drop the DB?
We've got you covered. Just set `postgresql[create_db]` to `false`
in the config.
