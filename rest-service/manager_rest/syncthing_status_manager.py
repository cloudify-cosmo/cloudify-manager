from datetime import datetime, timedelta

from flask import current_app

from cloudify.cluster_status import (ServiceStatus,
                                     NodeServiceStatus)

from manager_rest.storage import models, get_storage_manager
from manager_rest.rest.rest_utils import parse_datetime_string

try:
    from cloudify_premium import syncthing_utils
except ImportError:
    syncthing_utils = None


def _last_manager_in_cluster():
    storage_manager = get_storage_manager()
    managers = storage_manager.list(models.Manager,
                                    sort={'last_seen': 'desc'},
                                    get_all_results=True)
    active_managers = 0
    for manager in managers:
        # Probably new manager, first status report is yet to arrive
        if manager.status_report_frequency is None:
            active_managers += 1
        else:
            # The manager is considered active, if the time passed since
            # it's last_seen is maximum twice the frequency interval
            interval = manager.status_report_frequency * 2
            min_last_seen = datetime.utcnow() - timedelta(seconds=interval)

            if parse_datetime_string(manager.last_seen) > min_last_seen:
                active_managers += 1
        if active_managers > 1:
            return False
    return True


def _other_device_was_seen(syncthing_config, device_stats):
    # Add 1 second to the interval for avoiding false negative
    interval = syncthing_config['options']['reconnectionIntervalS'] + 1
    min_last_seen = datetime.utcnow() - timedelta(seconds=interval)

    for device_id, stats in device_stats.items():
        last_seen = parse_datetime_string(stats['lastSeen'])

        # Syncthing is valid when at least one device was seen recently
        if last_seen > min_last_seen:
            return True
    return False


def _is_syncthing_valid(syncthing_config, device_stats):
    """Checks that this syncthing has seen other devices, or is the only
    syncthing in the cluster."""
    if _other_device_was_seen(syncthing_config, device_stats):
        return True

    if _last_manager_in_cluster():
        current_app.logger.debug(
            'It is the last healthy manager in the cluster, no other '
            'devices were seen by File Sync Service'
        )
        return True

    current_app.logger.error(
        'Inactive File Sync Service - no other devices were seen by it'
    )
    return False


def get_syncthing_status():
    try:
        syncthing_config = syncthing_utils.config()
        device_stats = syncthing_utils.device_stats()
    except Exception as err:
        error_message = 'Syncthing check failed with {err_type}: ' \
                        '{err_msg}'.format(err_type=type(err),
                                           err_msg=str(err))
        current_app.logger.error(error_message)
        extra_info = {'connection_check': error_message}
        return NodeServiceStatus.INACTIVE, extra_info

    if _is_syncthing_valid(syncthing_config, device_stats):
        return (NodeServiceStatus.ACTIVE,
                {'connection_check': ServiceStatus.HEALTHY})

    return (NodeServiceStatus.INACTIVE,
            {'connection_check': 'No device was seen recently'})
