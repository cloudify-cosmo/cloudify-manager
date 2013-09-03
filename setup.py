__author__ = 'elip'

from setuptools import setup

setup(
    name='cosmo-plugin-installer',
    version='0.1.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['plugin_installer'],
    license='LICENSE',
    description='Plugin for installing plugins into an existing celery worker',
    install_requires=[
        "celery==3.0.19"
    ],
    tests_require=['nose']
)
