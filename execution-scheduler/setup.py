from setuptools import setup, find_packages

setup(
    name='cloudify-execution-scheduler',
    version='6.2.0',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'cloudify-execution-scheduler = execution_scheduler.main:cli',
        ]
    },
    install_requires=[
        'cloudify-rest-service==6.2.0',
    ],
)
