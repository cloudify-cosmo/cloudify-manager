__author__ = 'elip'

from setuptools import setup

PLUGINS_COMMON_VERSION = "3.0"
PLUGINS_COMMON_BRANCH = "develop"
PLUGINS_COMMON = "https://github.com/cloudify-cosmo/cloudify-plugins-common" \
                 "/tarball/{0}#egg=cloudify-plugins-common-{1}".format(
                     PLUGINS_COMMON_BRANCH, PLUGINS_COMMON_VERSION)

setup(
    name='cloudify-plugin-installer-plugin',
    version='3.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['plugin_installer'],
    license='LICENSE',
    description='Plugin for installing plugins into an existing celery worker',
    zip_safe=False,
    install_requires=[
        "cloudify-plugins-common"
    ],
    tests_require=[
        "nose"
    ],
    dependency_links=[PLUGINS_COMMON]
)
