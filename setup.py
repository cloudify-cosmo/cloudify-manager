import os
from os.path import join

from setuptools import setup, find_packages


# This makes sure to include all the config/scripts directories
# in the python package
def package_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            if filename.endswith('.pyc'):
                continue
            paths.append(join('..', path, filename))
    return paths


extra_files = package_files('cfy_install')
extra_files.append(join('..', 'config.json'))
extra_files.append(join('..', 'defaults.json'))


setup(
    name='cloudify-manager-install',
    version='0.2',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(),
    license='LICENSE',
    description='Local install of a cloudify manager',
    entry_points={
        'console_scripts': [
            'cfy_install = cfy_install.main:install',
            'cfy_remove = cfy_install.main:remove',
            'cfy_config = cfy_install.main:configure'
        ]
    },
    zip_safe=False,
    package_data={'': extra_files},
)
