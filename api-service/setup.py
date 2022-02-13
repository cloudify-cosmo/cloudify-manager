from setuptools import find_packages, setup

setup(
    name='cloudify-api',
    version='6.3.1',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(
        include='cloudify_api*', exclude=('cloudify_api.tests*',)
    ),
    description='Cloudify API',
    install_requires=[
        'fastapi',
        'async-exit-stack',
        'async-generator',
        'SQLAlchemy',
        'asyncpg',
        'uvicorn[standard]',
        'cloudify-rest-service',
        ],
    test_requires=[
        'mock',
        'pytest',
    ]
)
