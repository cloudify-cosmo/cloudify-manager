
__author__ = "idanmo"

from setuptools import setup

RIEMANN_CONFIGURER_VERSION = "0.1.1"
RIEMANN_CONFIGURER = "https://github.com/CloudifySource/cosmo-plugin-riemann-configurer/tarball/{0}".format(
    RIEMANN_CONFIGURER_VERSION)

PLUGIN_INSTALLER_VERSION = "0.1.0"
PLUGIN_INSTALLER = "https://github.com/CloudifySource/cosmo-plugin-plugin-installer/tarball/{0}".format(
    PLUGIN_INSTALLER_VERSION)

setup(
    name='cloudify-workflows',
    version='0.1.0',
    author='Idan Moyal',
    author_email='idan@gigaspaces.com',
    packages=['tests'],
    license='LICENSE',
    description='Cloudify workflow python tests',
    install_requires=[
        "celery",
        "bernhard",
        "cosmo-plugin-riemann-configurer",
        "cosmo-plugin-plugin-installer",
        "nose"
    ],

    dependency_links=[
        "{0}#egg=cosmo-plugin-riemann-configurer-{1}".format(RIEMANN_CONFIGURER,
                                                                           RIEMANN_CONFIGURER_VERSION),
        "{0}#egg=cosmo-plugin-plugin-installer-{1}".format(PLUGIN_INSTALLER,
                                                             PLUGIN_INSTALLER_VERSION)
    ]
)