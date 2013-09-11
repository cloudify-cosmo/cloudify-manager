import subprocess

__author__ = 'elip'

from setuptools import setup

FABRIC_RUNNER = "https://github.com/CloudifySource/cosmo-fabric-runner/archive/feature/CLOUDIFY-2022-initial-commit.zip"


def run_command(command):
    p = subprocess.Popen(command.split(" "), stdout=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise RuntimeError("Failed running command {0} [returncode={1}, "
                           "output={2}, error={3}]".format(command, out, err, p.returncode))
    return out

run_command("sudo pip install {0}".format(FABRIC_RUNNER))

setup(
    name='cosmo-plugin-agent-installer',
    version='0.1.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['worker_installer'],
    license='LICENSE',
    description='Plugin for starting a new cosmo agent on a remote host',
    install_requires=[
        "celery"
    ]
)




