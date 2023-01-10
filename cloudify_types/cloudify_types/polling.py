import time

from cloudify import ctx
from .constants import POLLING_INTERVAL
from cloudify.exceptions import NonRecoverableError
from cloudify.models_states import BlueprintUploadState


def poll_with_timeout(pollster,
                      timeout,
                      interval=POLLING_INTERVAL,
                      expected_result=True):
    # Check if timeout value is -1 that allows infinite timeout
    # If timeout value is not -1 then it is a finite timeout
    timeout = float('infinity') if timeout == -1 else timeout
    current_time = time.time()

    ctx.logger.debug('Polling with timeout of %s seconds', timeout)

    while time.time() <= current_time + timeout:
        if pollster() != expected_result:
            ctx.logger.debug('Polling...')
            time.sleep(interval)
        else:
            ctx.logger.debug('Polling succeeded!')
            return True

    ctx.logger.error('Polling timed out!')
    return False


def verify_blueprint_uploaded(blueprint_id, client):
    blueprint = client.blueprints.get(blueprint_id)
    state = blueprint['state']
    if state in BlueprintUploadState.FAILED_STATES:
        raise NonRecoverableError(
            f'Blueprint {blueprint_id} upload failed (state: {state})')
    return state == BlueprintUploadState.UPLOADED


def wait_for_blueprint_to_upload(
        blueprint_id, client, timeout_seconds=30):
    result = poll_with_timeout(
        lambda: verify_blueprint_uploaded(blueprint_id, client),
        timeout=timeout_seconds,
        interval=POLLING_INTERVAL)
    if not result:
        raise NonRecoverableError(
            f'Blueprint upload timed out after: {timeout_seconds} seconds.')
    return True
