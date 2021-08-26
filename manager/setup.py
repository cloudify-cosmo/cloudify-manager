from setuptools import setup, find_packages

DEPENDENCIES = [
    'fastapi',
    'async-exit-stack',
    'async-generator',
    'SQLAlchemy>',
    'uvicorn',
    'cloudify-rest-service',
]

setup(
    name='cloudify-manager-service',
    version='6.2.0.dev1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(
        include='manager_service*', exclude=('manager_service.tests*',)
    ),
    description='Cloudify Manager Service',
    install_requires=DEPENDENCIES,
)
