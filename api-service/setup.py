from setuptools import setup, find_packages

DEPENDENCIES = [
    'fastapi',
    'async-exit-stack',
    'async-generator',
    'SQLAlchemy',
    'asyncpg',
    'uvicorn',
    'cloudify-rest-service',
]

setup(
    name='cloudify-api',
    version='6.2.0.dev1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(
        include='cloudify_api*', exclude=('cloudify_api.tests*',)
    ),
    description='Cloudify Manager Service',
    install_requires=DEPENDENCIES,
)
