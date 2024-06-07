RoboTA Core - Provider Agnostic Retrieval of Git-Based Software Artefacts
=========================================================================

RoboTA Core is a Python module that supports analysis of a range of artefacts usually stored
in a hosted Git-based software project.  It provides a common single data model for commit data,
issue data, merge/pull requests, CI results, wiki pages, etc., independent of the underlying
hosting system.  It is designed to be provider agnostic; for example, artefacts can come from
GitLab or GitHub hosted projects, or a locally hosted Git project.  CI data is currently
only accessible from Jenkins.

Its aim is to facilitate inter- and intra-project analysis of software engineering practices
and outcomes.  The module originated in the RoboTA project undertaken at the University of
Manchester, to provide a framework for the automated assessment of software engineering
coursework though it has a wider scope in the assessment of general good practice in software
engineering.  RoboTA (pronounced a bit like "Roberta") is short for Robot Teaching Assistant.
The RoboTA suite of tools includes robota-marking (which assigns marks to projects based on
a configurable marking scheme, expressed in YAML), robota-progress (which provides a simple
progress dashboard for team-based student projects) and robota-common-errors (which
reports on instances of common errors found in student code bases and projects).

RoboTA Core is a foundational component of all these tools, provided the base data about
the project for the higher level analysis tools to use.

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

RoboTA Core requires access to a number of data sources to collect data to operate on. 
Details of these data sources and information required to connect to them is provided in the robota config yaml file.
Documentation on the config file can be found in the _data_sources_ section of the documentation.
RoboTA config template files are provided with the robota-common-errors, robota-progress and robota-marking packages.
