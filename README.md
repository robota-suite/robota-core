RoboTA - Automated software engineering aseessment
----------------------------------------------------
RoboTA (Robot Teaching Assistant) is a Python module to provide a framework for the assessment of 
software engineering. The focus of RoboTA is the assessment of student software engineering courswork,
though it has a wider scope in the assessment of general good practice in software engineering.

The robota-core package collects information about a project from a number of sources, git repositories, 
issue trackers, ci-servers. It is designed to be provider agnostic, for example repository data can come from GitLab
or GitHub.

There then a number of other RoboTA packages that use this information to assess project quality.
robota-common-errors identifies common errors in software engineering workflows.
robota-progress provides a simple progress dashboard for a project.
robota-marking provides a framework for the assessment of student coursework.

RoboTA was developed in the [Computer Science](https://www.cs.manchester.ac.uk/) department 
at the [University of Manchester](https://www.manchester.ac.uk/).
From 2018 to March 2021, development of RoboTA was funded by the [Institute of Coding](https://ioc.cs.manchester.ac.uk/).

Installation
-------------

To install as a Python module, type

`python -m pip install robota-core`

from the root directory. 
For developers, you should install in linked .egg mode using

`python -m pip install robota-core -e`

If you are using a Python virtual environment, you should activate this first before using the above commands.

RoboTA Config
--------------

RoboTA requires access to a number of data sources to collect data to operate on. 
Details of these data sources and information required to connect to them is provided in the robota config yaml file.
Documentation on the config file can be found in the _data_sources_ section of the documentation.
RoboTA config template files are provided with the robota-common-errors, robota-progress and robota-marking packages.