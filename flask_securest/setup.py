"""
Flask-SQLite3
-------------

This is the description for that library
"""
from setuptools import setup


setup(
    name='Flask-SecuREST',
    version='0.5',
    # url='http://example.com/flask-securest/',
    # license='BSD',
    author='noak',
    author_email='noak@gigaspaces.com',
    # description='Securing Flask REST applications',
    # long_description=__doc__,
    # if you would be using a package instead use packages instead
    # of py_modules:
    packages=['flask_securest'],
    # zip_safe=False,
    # include_package_data=True,
    # platforms='any',
    install_requires=[
        'Flask>=0.9',
        'Flask-RESTful',
    ],
    classifiers=[
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        # 'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ]
)
