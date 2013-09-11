__author__ = 'elip'

from setuptools import setup

FABRIC_RUNNER = "https://github.com/CloudifySource/cosmo-fabric-runner/tarball/feature/CLOUDIFY-2022-initial-commit"
FABRIC_RUNNER_VERSION = "0.1.0"

setup(
    name='cosmo-plugin-agent-installer',
    version='0.1.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['worker_installer'],
    license='LICENSE',
    description='Plugin for starting a new cosmo agent on a remote host',
    install_requires=[
        "cosmo-fabric-runner",
        "celery"
    ],
    dependency_links=["{0}#egg=cosmo-fabric-runner-{1}".format(FABRIC_RUNNER, FABRIC_RUNNER_VERSION)]
)




