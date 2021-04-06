#!/usr/bin/env python
import setuptools
from irrd import __version__

with open('README.rst', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='irrd',
    version=__version__,
    author='DashCare for NTT Ltd.',
    author_email='irrd@dashcare.nl',
    description='Internet Routing Registry daemon (IRRd)',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/irrdnet/irrd',
    packages=setuptools.find_packages(
        exclude=['*.tests', '*.tests.*', 'tests.*', 'tests', 'irrd.integration_tests']
    ),
    python_requires='>=3.6',
    package_data={'': ['*.txt', '*.yaml', '*.mako']},
    install_requires=[
        # This list must be kept in sync with requirements.txt version-wise,
        # but should not include packages used for testing, generating docs
        # or packages.
        'python-gnupg==0.4.7',
        'passlib==1.7.4',
        'IPy==1.01',
        'ordered-set==4.0.2',
        'beautifultable==0.8.0',
        'PyYAML==5.4.1',
        'datrie==0.8.2',
        'setproctitle==1.2.2',
        'python-daemon==2.3.0',
        'pid==3.0.4',
        'redis==3.5.3',
        'hiredis==2.0.0',
        'requests==2.25.1',
        'pytz==2021.1',
        'ariadne==0.13.0',
        'uvicorn==0.13.4',
        'starlette==0.14.2',
        'psutil==5.8.0',
        'asgiref==3.3.1',
        'pydantic==1.8.1',
        'SQLAlchemy==1.3.24',
        'alembic==1.5.8',
        'ujson==4.0.2',
    ],
    extras_require={
        ':python_version < "3.7"': [
            'dataclasses==0.8',
        ],
        ':python_version > "3.7"': [
            'uvicorn[standard]==0.13.4',
        ],
        ':platform_python_implementation == "CPython"': [
            'psycopg2-binary==2.8.6',
        ],
        ':platform_python_implementation == "PyPy"': [
            'psycopg2cffi==2.9.0',
        ],
    },
    entry_points={
        'console_scripts': [
            'irrd = irrd.daemon.main:main',
            'irrd_submit_email = irrd.scripts.submit_email:main',
            'irrd_database_upgrade = irrd.scripts.database_upgrade:main',
            'irrd_database_downgrade = irrd.scripts.database_downgrade:main',
            'irrd_load_database = irrd.scripts.load_database:main',
            'irrd_update_database = irrd.scripts.update_database:main',
            'irrd_set_last_modified_auth = irrd.scripts.set_last_modified_auth:main',
            'irrd_mirror_force_reload = irrd.scripts.mirror_force_reload:main',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Operating System :: OS Independent',
    ],
)
