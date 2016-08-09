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
            from flask import Flask
            from flask import request
            from flask import json
            from flask import request, redirect, url_for, render_template
            from flask_sqlalchemy import SQLAlchemy
            from sqlalchemy import exists
            from flask_script import Manager
            from flask_migrate import Migrate, MigrateCommand
            self.logger.info('bbbbbbbbbbbbbbbbbbbbbbb ')
        except Exception as e:
            self.logger.info('bbbbbbbbbbbbbbbbbbbbbbb - failed to import psycopg2')
            raise e
