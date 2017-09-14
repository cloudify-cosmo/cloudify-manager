
from requests import post

from .. import acfy, helptexts
from ..utils import get_auth_header


@acfy.group(name='snapshots')
@acfy.options.verbose()
def snapshots():
    """Handle manager snapshots
    """
    pass


@snapshots.command(name='restore',
                   short_help='Restore a manager from a snapshot')
@acfy.argument('snapshot-id')
@acfy.options.without_deployment_envs
@acfy.options.force(help=helptexts.FORCE_RESTORE_ON_DIRTY_MANAGER)
@acfy.options.restore_certificates
@acfy.options.no_reboot
@acfy.options.verbose()
@acfy.pass_logger
def restore(snapshot_id,
            without_deployment_envs,
            force,
            restore_certificates,
            no_reboot,
            logger):
    """Restore a manager to its previous state

    `SNAPSHOT_ID` is the id of the snapshot to use for restoration.
    """
    logger.info('Restoring snapshot {0}...'.format(snapshot_id))
    data = {
        'recreate_deployments_envs': not without_deployment_envs,
        'force': force,
        'restore_certificates': restore_certificates,
        'no_reboot': no_reboot
    }
    response = post(
        'http://127.0.0.1:80/api/v3.1/snapshots/{0}/restore'.format(
            snapshot_id),
        json=data, headers=get_auth_header(), verify=False
    )
    logger.info("Started workflow execution. The execution's id is {0}".format(
        response.content['id']))
    if not restore_certificates:
        return
    if no_reboot:
        logger.warn('Certificates might be replaced during a snapshot '
                    'restore action. It is recommended that you reboot the '
                    'Manager VM when the execution is terminated, or several '
                    'services might not work.')
    else:
        logger.info('In the event of a certificates restore action, the '
                    'Manager VM will automatically reboot after execution is '
                    'terminated. After reboot the Manager can work with the '
                    'restored certificates.')
