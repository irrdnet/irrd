#!/usr/bin/env python
import setuptools
from irrd import __version__

with open('README.rst', 'r') as fh:
    long_description = fh.read()

setuptools.setup(
    name='irrd',
    version=__version__,
    author='Reliably Coded for NTT Ltd. and others',
    author_email='irrd@reliablycoded.nl',
    description='Internet Routing Registry daemon (IRRd)',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/irrdnet/irrd',
    packages=setuptools.find_packages(
        exclude=['*.tests', '*.tests.*', 'tests.*', 'tests', 'irrd.integration_tests']
    ),
    python_requires='>=3.7',
    package_data={'': ['*.txt', '*.yaml', '*.mako']},
    install_requires=[
        # This list must be kept in sync with requirements.txt version-wise,
        # but should not include packages used for testing, generating docs
        # or packages.
        'python-gnupg==0.5.0',
        'passlib==1.7.4',
        'bcrypt==4.0.1',
        'IPy==1.01',
        'ordered-set==4.1.0',
        'beautifultable==0.8.0',
        'PyYAML==6.0',
        'datrie==0.8.2',
        'setproctitle==1.3.2',
        'python-daemon==2.3.2',
        'pid==3.0.4',
        'redis==4.5.1',
        'hiredis==2.2.2',
        'coredis==4.10.2',
        'requests==2.28.2',
        'pytz==2022.7.1',
        'ariadne==0.17.1',
        'uvicorn==0.20.0',
        'starlette==0.20.4',
        'psutil==5.9.4',
        'asgiref==3.6.0',
        'pydantic==1.10.5',
        'typing-extensions==4.5.0',
        'py-radix-sr==1.0.0post1',
        'SQLAlchemy==1.3.24',
        'alembic==1.9.4',
        'ujson==5.7.0',
        'wheel==0.38.4',
    ],
    extras_require={
        ':python_version > "3.7"': [
            'uvicorn[standard]==0.20.0',
        ],
        ':python_version < "3.8"': [
            'websockets==10.4',
        ],
        ':platform_python_implementation == "CPython"': [
            'psycopg2-binary==2.9.5',
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
            'irrd_expire_journal = irrd.scripts.expire_journal:main',
            'irrd_mirror_force_reload = irrd.scripts.mirror_force_reload:main',
            'irr_rpsl_submit = irrd.scripts.irr_rpsl_submit:main',
            'irrd_load_pgp_keys = irrd.scripts.load_pgp_keys:main',
        ],
    },
    classifiers=[
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: OS Independent',
    ],
)
