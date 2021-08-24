from setuptools import setup, find_packages

CLOUDIFY_VERSION = '6.2.0.dev1'

DEPENDENCIES = [
    'fastapi>=0.68.0,<1',
    'async-exit-stack>=1.0.1,<2',
    'async-generator>=1.10,<2',
    'SQLAlchemy>=1.4.22,<2',
    'uvicorn>=0.15.0,<1',
    f'cloudify-rest-service=={CLOUDIFY_VERSION}'
]

setup(
    name='cloudify-manager-service',
    version=CLOUDIFY_VERSION,
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(
        include='manager_service*', exclude=('manager_service.tests*',)
    ),
    description='Cloudify Manager Service',
    install_requires=DEPENDENCIES,
)
