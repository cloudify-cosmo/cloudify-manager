
VERBOSE = \
    "Show verbose output. You can supply this up to three times (i.e. -vvv)"
VERSION = (
    "Display the version and exit (if a manager is used, its version will "
    "also show)"
)
NODE_NAME = 'Name of a cluster node'
HOST_IP = 'IP of the machine'
MANAGER_USERNAME = 'Manager username used to run commands on the manager'
MANAGER_PASSWORD = 'Manager password used to run commands on the manager'
MASTER_IP = 'IP address of the cluster master'
WITH_MANAGER_DEPLOYMENT = 'Include the manager_deployment in the output'
LDAP_SERVER = 'The LDAP server address to authenticate against'
LDAP_USERNAME = 'The LDAP admin username to be set on the Cloudify manager'
LDAP_PASSWORD = 'The LDAP admin password to be set on the Cloudify manager'
LDAP_DOMAIN = 'The LDAP domain to be used by the server'
LDAP_IS_ACTIVE_DIRECTORY = 'Specify whether the LDAP used for authentication' \
                           ' is Active-Directory.'
LDAP_DN_EXTRA = 'Extra LDAP DN options.'
RESTORE_SNAPSHOT_EXCLUDE_EXISTING_DEPLOYMENTS = (
    "Restore without recreating the currently existing deployments"
)
FORCE_RESTORE_ON_DIRTY_MANAGER = (
    "Restore a snapshot on a manager where there are existing blueprints or "
    "deployments"
)
RESTORE_CERTIFICATES = 'Restore the certificates from the snapshot, using ' \
                       'them to replace the current Manager certificates. ' \
                       'If the certificates` metadata (I.E: the Manager IP ' \
                       'address) from the snapshot does not match the ' \
                       'Manager metadata, the certificates cannot work on ' \
                       'this Manager and will not be restored. In the event ' \
                       'that the certificates have been restored, the ' \
                       'Manager will be automatically rebooted at the end ' \
                       'of the execution. To avoid automatic reboot, use ' \
                       'the flag `--no-reboot` (not recommended)'
NO_REBOOT = 'Do not perform an automatic reboot to the Manager VM after ' \
            'restoring certificates a from snapshot (not recommended). ' \
            'Only relevant if the `--restore-certificates` flag was supplied'
CERT_PATH = 'Path to the certificate file'
KEY_PATH = 'Path to the key file'
