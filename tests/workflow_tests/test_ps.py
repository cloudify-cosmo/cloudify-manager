import os
import uuid
import errno
import tarfile
import tempfile
from contextlib import contextmanager

from cloudify import context
from cloudify_rest_client.exceptions import CloudifyClientError
from cloudify_rest_client.executions import Execution

from testenv import TestCase
from testenv.utils import (
    get_resource, do_retries, timeout, delete_deployment,
    verify_deployment_environment_creation_complete,
    deploy_application, undeploy_application,
)



class TestPS(TestCase):

    def test_ps_exist(self):
        try:
            self.logger.info('aaaaaaaaaaaaaaaaaaaaa ')
            import psycopg2
            self.logger.info('bbbbbbbbbbbbbbbbbbbbbbb ')
        except Exception as e:
            self.logger.info('bbbbbbbbbbbbbbbbbbbbbbb - failed to import psycopg2')
            raise e
