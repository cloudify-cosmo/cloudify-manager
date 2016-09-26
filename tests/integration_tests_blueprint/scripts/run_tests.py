#!/usr/bin/env python
import os
from os.path import join, dirname

from cloudify import ctx
ctx.download_resource(
        join('scripts', 'utils.py'),
        join(dirname(__file__), 'utils.py'))
import utils  # noqa

tests_descriptor = ctx.node.properties['test_suites']


def run_integration_tests():
    ctx.logger.info('Running integration tests {0}'.format(tests_descriptor))
    remote_script_path = join(utils.WORKDIR, 'run_tests.sh')
    ctx.download_resource(join('scripts', 'run_tests.sh'), remote_script_path)
    utils.run('chmod +x {0}'.format(remote_script_path))

    manager_test_path = os.path.join(utils.REPOS_DIR,
                                     'cloudify-manager',
                                     'tests', 'integration_tests', 'framework')
    suites_runner_path = os.path.join(manager_test_path, 'suites_runner.py')

    utils.run('{0} {1} {2} {3}'.format(remote_script_path,
                                       utils.CLOUDIFY_VENV_PATH,
                                       suites_runner_path,
                                       tests_descriptor),
              out=True)


def main():
    if tests_descriptor:
        run_integration_tests()

main()
