# /setup.py
"""
Setup configuration for HiveCtl.
"""
from setuptools import setup, find_namespace_packages
from pathlib import Path

# Read version from hivectl.py
with open('hivectl/hivectl.py', 'r') as f:
    for line in f:
        if line.startswith('VERSION'):
            version = line.split('=')[1].strip().strip('"\'')
            break

# Read README
readme = Path(__file__).parent / 'README.md'
long_description = readme.read_text() if readme.exists() else ''

setup(
    name='hivectl',
    version=version,
    description='Management tool for containerized infrastructure',
    long_description=long_description,
    long_description_content_type='text/markdown',
    author='We4Bee Team',
    author_email='dev@we4bee.org',
    url='https://github.com/itsatony/w4b_v3/server/w4bcontainers/hivectl',
    packages=find_namespace_packages(include=['hivectl', 'hivectl.*']),
    include_package_data=True,
    python_requires='>=3.8',
    install_requires=[
        'click>=8.1.7',
        'rich>=13.7.0',
        'pyyaml>=6.0.1',
        'python-dotenv>=1.0.0'
    ],
    entry_points={
        'console_scripts': [
            'hivectl=hivectl:cli'
        ]
    },
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Monitoring',
        'Topic :: System :: Installation/Setup',
    ],
    keywords='container management, infrastructure, monitoring, podman',
    project_urls={
        'Documentation': 'https://github.com/itsatony/w4b_v3/server/w4bcontainers/hivectl/wiki',
        'Source': 'https://github.com/itsatony/server/w4bcontainers/w4b_v3/hivectl',
        'Tracker': 'https://github.com/itsatony/server/w4bcontainers/w4b_v3/hivectl/issues',
    },
    zip_safe=False,
    package_data={
        'hivectl': [
            'config/*.yaml',
            'logs/.gitkeep'
        ]
    }
)