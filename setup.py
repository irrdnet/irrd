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
    url='https://github.com/irrdnet/irrd4',
    packages=setuptools.find_packages(
        exclude=['*.tests', '*.tests.*', 'tests.*', 'tests', 'irrd.integration_tests']
    ) + ['twisted.plugins'],
    python_requires='>=3.6',
    package_data={'': ['*.txt', '*.yaml', '*.mako']},
    install_requires=[
        # This list must be kept in sync with requirements.txt version-wise,
        # but should not include packages used for testing, generating docs
        # or packages.
        'python-gnupg==0.4.5',
        'passlib==1.7.1',
        'IPy==1.00',
        'dataclasses==0.7',
        'ordered-set==3.1.1',
        'dotted==0.1.8',
        'beautifultable==0.8.0',
        'PyYAML==5.1.2',
        'psycopg2-binary==2.8.4',
        'SQLAlchemy==1.3.10',
        'alembic==1.3.0',
        'ujson==1.35',
        'twisted==19.7.0',
    ],
    entry_points={
        'console_scripts': [
            'irrd_submit_email = irrd.scripts.submit_email:main',
            'irrd_database_upgrade = irrd.scripts.database_upgrade:main',
            'irrd_load_database = irrd.scripts.load_database:main',
            'irrd_mirror_force_reload = irrd.scripts.mirror_force_reload:main',
        ],
    },
    classifiers=(
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Operating System :: OS Independent',
    ),
)
