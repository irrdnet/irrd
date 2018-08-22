#!/usr/bin/env python
import setuptools
from irrd import __version__

with open('README.rst', 'r') as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()

setuptools.setup(
    name='irrd',
    version=__version__,
    author='DashCare for NTT Communications',
    author_email='irrd@dashcare.nl',
    description='Internet Routing Registry Daemon (IRRd)',
    long_description=long_description,
    long_description_content_type='text/x-rst',
    url='https://github.com/irrdnet/irrd4',
    packages=setuptools.find_packages(),
    python_requires='>=3.6',
    install_requires=required,
    data_files=[('', ['LICENSE'])],
    entry_points={
        'console_scripts': [
            'rpsl_read = irrd.scripts.rpsl_read:main',
        ],
    },
    classifiers=(
        'Development Status :: 2 - Pre-Alpha',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Operating System :: OS Independent',
    ),
)
