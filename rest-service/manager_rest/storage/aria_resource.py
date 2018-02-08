import aria
from aria.storage.filesystem_rapi import FileSystemResourceAPI

# Use a synced directory
STORAGE_DIR = '/opt/manager/resources/aria'

_resource_storage = None


def resource_storage():
    """Get aria resource storage.

    The resource storage is used to access artifacts that are replicated
    through HA.

    :return: Aria resource storage
    :rtype: :class:`aria.storage.core.ResourceStorage`

    """
    global _resource_storage
    if _resource_storage is None:
        _resource_storage = aria.application_resource_storage(
            api=FileSystemResourceAPI,
            api_kwargs={'directory': STORAGE_DIR},
        )

    return _resource_storage
