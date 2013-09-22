
__author__ = "idanmo"

from setuptools import setup
import os
import sys


def pip_install(url):
    os.system("pip install {0}".format(url))

os.chdir(sys.path[0])

# The following plugins are installed using pip because their installation is required to be flat (not egg)
# as these plugins are copied from python lib in tests runtime.
pip_install("https://github.com/CloudifySource/cosmo-plugin-plugin-installer/archive/0.1.0.zip")
pip_install("https://github.com/CloudifySource/cosmo-plugin-riemann-configurer/archive/0.1.1.zip")

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
        "nose"
    ],
)