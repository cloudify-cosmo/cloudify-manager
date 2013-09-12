import os

__author__ = 'elip'

from setuptools import setup

DEFAULT_BRANCH = "feature/CLOUDIFY-2022-initial-commit"

BRANCH = os.environ.get("COSMO_BRANCH", DEFAULT_BRANCH)

COSMO_CELERY = "https://github.com/CloudifySource/cosmo-celery-common/tarball/{0}".format(BRANCH)
COSMO_CELERY_VERSION = "0.1.0"

setup(
    name='cosmo-plugin-plugin-installer',
    version='0.1.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['plugin_installer'],
    license='LICENSE',
    description='Plugin for installing plugins into an existing celery worker',
    install_requires=[
        "celery",
        # we add this to allow running the plugin installer from outside of the cosmo env.
        # this will bring the necessary dependencies
        "cosmo-celery-common"
    ],

    dependency_links=["{0}#egg=cosmo-celery-common-{1}".format(COSMO_CELERY, COSMO_CELERY_VERSION)]
)
