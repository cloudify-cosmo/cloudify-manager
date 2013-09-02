__author__ = 'elip'

from setuptools import setup

setup(
    name='cosmo-plugin-python-webserver',
    version='0.1.0',
    author='elip',
    author_email='elip@gigaspaces.com',
    packages=['python_webserver_installer'],
    license='LICENSE',
    description='Plugin for starting a simple python webserver on the localhost',
    install_requires=[
        "Flask"
    ],
    tests_require=['nose']
)
