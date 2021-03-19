RoboTA data types and data sources
--------------------------------------

RoboTA reads in various types of data from different sources.
This could be data about software engineering objects such as git commits or it could
be about the human elements of software engineering such as interactions with an
issue board or bug tracker.

In order to be as flexible as possible, you can specify different sources for each of these data types.

Data types
============
Each data type provides a different type of information to RoboTA that is used somewhere in the code.
Depending on what parts of RoboTA are being used, not all the data types may be required. 

**Every data type requires a 'data_source' key which says where the data comes from.**
Some data types have additional keys which are required to specify details of the data type.

Not all methods of each data type are implemented for every data source, for example a
'local_repository' type repository does not provide information on pull/merge requests. In these cases
attempting to use an invalid method will raise a Python NotImplementedError.

marking_config
##################
The location of the set up files for RoboTA marking.

Valid data sources: local, gitlab

Required keys:

* course_config_file: The path of the Course config file
* mark_scheme_file: The path of the file that specifies the mark scheme 
* build_config_file: The path to the file that has information about the build config
 
issues
##########
The location of issues. Issues are used in marking students planning and teamwork.

Valid sources: gitlab, github

ci
####
A CI server hosting tests assessing student code.

Valid sources: jenkins

repository
###########
A source of information about commits, tags, events, branches and files 
in the student work repository.

Valid sources: gitlab, github, local_repository

remote_provider
#################
A cloud provider that hosts git repositories. Provides info about pull/merge requests and team members

Valid sources: gitlab, github

attendance
###########
Information about student attendance at a class, workshop or event

Valid sources: benchmark

student_details
################
Information about student names and usernames

Valid sources: gitlab

student_emails
##################
The relationship between student usernames and email addresses

Valid sources: gitlab

required keys:

* name_list_file - The path of the file containing the mapping between names and email addresses

ta_marks
##########
Manually assigned marks that can be used to override RoboTA marks in the marking report

Valid sources: gitlab, local

required keys:

* ta_marks_file - The path of the file containing the TA marks.

gitlab_tests
#############
Connection to a test repository to test functions of the code relating to gitlab

Valid sources: gitlab

Data Sources
=============

Each data source specified in a data type should correspond to a data source in the data sources section.
For flexibility the data sources are specified by name which means that each data source could be used for 
multiple data types.

Each data source has a type. Each data source type is treated differently by the code.

The different data sources are:

* local_path
* gitlab
* github
* local_repository
* jenkins
* benchmark

Below are specified the keys which are required for each data source type.

local_path
############
Download files from a local directory on the machine on which RoboTA is running.

required sub-values:

* path - The path to look in for the file(s). 

gitlab
##########
Connect to a remote gitlab instance to retrieve information or files.

required sub-values:

* url: The url of the gitlab instance
* project: The name of the gitlab project to load
* token: An authentication token to connect to the gitlab instance

optional sub-values:

* branch: Which git branch to assess - defaults to 'master'

github
#########
Connect to a remote GitHub instance to retrieve information or files.

required sub-values:

* url: The url of the GitHub instance
* project: The name of the GitHub project to load
* token: An authentication token to connect to the GitHub instance

optional sub-values:

* branch: Which git branch to assess - defaults to 'master'

local_repository
###################
Connect to a repository on the local machine.

required sub-values:

* path: The path of the git repository.

optional sub-values:

* branch: Which branch to consider - defaults to 'master'

jenkins
#########
Connect to a remote Jenkins instance to retrieve job information

required sub-values:

* url: The url of the Jenkins instance
* username: Username used for authentication
* token: Token used for authentication    
* project_name: The name of the project containing the tests
* folder_name: The name of the folder in the project containing the tests

benchmark
#############
A University of Manchester service that has information about students

required sub-values:

* url: The URL of the benchmark instance
* token: Token used for authentication

Note that a connection to benchmark requires either being on campus or use of the UoM VPN.

Variable Substitution
=========================
To improve automation, named keys in the config file can be specified which are replaced by values at
run time. Strings to be substituted should be enclosed in curly brackets. Replacement values should be
specified as command line arguments.

Example Config
================
.. code-block:: YAML

    # This is an example robota config file.
    # This file is used it to store RoboTA config variables and credentials locally.
    # You should NOT commit any credentials to git.

    # The 'data_types' section specifies where the data to run RoboTA comes from. The keys are
    the data type and are fixed as they are specified in the code.
    # The data source key is mandatory for each data type. Other key: value pairs are passed
    # into the code to be used for configuration of that data type.

    data_types:
        issues:
            data_source: github_repo
        repository:
            data_source: github_repo
        remote_provider:
            data_source: github_repo
        common_errors:
            data_source: local_errors
            file_name: error_definitions.yaml


    # Details of data sources. The name of each data source corresponds to those specified in the data_types section above.
    # Keys and values are specific to the data source.

    data_sources:
        github_repo:
            type: github
            url: www.github.com
            project: merrygoat/chi4
            token: xxx-xxx-xxx

        local_errors:
            type: local_path
            directory: C:/robota/robota-common-errors
