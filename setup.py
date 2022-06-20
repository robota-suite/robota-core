from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='robota_core',
    version='2.2.2',
    description='An automated assessment and progress monitoring tool.',
    long_description=long_description,
    long_description_content_type="text/markdown",
    author='University of Manchester',
    url='https://gitlab.cs.man.ac.uk/institute-of-coding/robota-core',
    packages=find_packages(),
    install_requires=['requests',
                      'jinja2',
                      'python-gitlab==2.10.1',
                      'PyYaml>=5.1',
                      'pytest',
                      'gitpython',
                      'python-jenkins',
                      'python-dateutil',
                      'bleach',
                      'Markdown',
                      'PyGithub',
                      'loguru',
                      'dateparser'
                      ]
)
