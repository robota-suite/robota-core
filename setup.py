from setuptools import setup, find_packages

setup(
    name='robota_core',
    version='2.0.0',
    description='An automated assessment and progress monitoring tool.',
    author='University of Manchester',
    packages=find_packages(),
    install_requires=['jinja2',
                      'python-gitlab==1.8.0',
                      'PyYaml>=5.1',
                      'pytest',
                      'gitpython',
                      'requests',
                      'python-jenkins',
                      'python-dateutil',
                      'bleach',
                      'Markdown',
                      'PyGithub',
                      'pygit2',
                      'loguru'
                      ]
)
