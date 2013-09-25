__author__ = 'elip'

from setuptools import setup

COSMO_CELERY_VERSION = "0.1.0"
COSMO_CELERY = "https://github.com/CloudifySource/cosmo-celery-common/tarball/{0}".format("develop")

setup(
    name='cosmo-plugin-plugin-installer',
    version='0.1.1',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['plugin_installer'],
    license='LICENSE',
    description='Plugin for installing plugins into an existing celery worker',
    zip_safe=False,
    install_requires=[
        "cosmo-celery-common"
    ],

    dependency_links=["{0}#egg=cosmo-celery-common-{1}".format(COSMO_CELERY, COSMO_CELERY_VERSION)]
)
