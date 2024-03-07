from setuptools import find_packages, setup

setup(
    name='cloudify-api',
    version='7.0.4',
    author='Cloudify',
    author_email='cosmo-admin@cloudify.co',
    packages=find_packages(
        include='cloudify_api*', exclude=('cloudify_api.tests*',)
    ),
    description='Cloudify API',
    install_requires=[
        'SQLAlchemy',
        'async-exit-stack',
        'async-generator',
        'asyncpg',
        'cloudify-rest-service',
        'fastapi',
        'uvicorn[standard]',
    ],
    test_requires=[
        'mock',
        'pytest',
    ]
)
