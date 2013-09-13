import os
import subprocess

__author__ = 'elip'

DEFAULT_BRANCH = "feature/CLOUDIFY-2022-initial-commit"

BRANCH = os.environ.get("COSMO_BRANCH", DEFAULT_BRANCH)


def update_worker():

    """
    Use this method to connect to an existing management machine and update the worker with new plugins from
    github.
    Be sure to push your changes before running this.
    """
    from test import get_remote_runner
    runner = get_remote_runner()
    runner.run("export COSMO_BRANCH={0} "
               "&& python2.7 /vagrant/bootstrap_lxc_manager.py --update_only=True".format(BRANCH))


update_worker()