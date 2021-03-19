"""A module for visualising the commits in git repositories and their relations."""
import datetime
import subprocess
from typing import List, TextIO, Tuple

from robota_core.config_readers import get_robota_config
from robota_core.repository import new_repository


def catch_empty_graph(nodes, all_commits, commit_parents):
    """If there are no branches and no tags, print the commits starting from the oldest."""
    if not nodes:
        parent_id = all_commits[-1]
        commit_list = [parent_id]
        parents = True
        while parents:
            if parent_id in all_commits:
                parent_index = all_commits.index(parent_id)
                parents = commit_parents[parent_index]
                parent_id = parents[0]
                commit_list.append(parent_id)
            else:
                parents = False
        nodes.append(list(reversed(commit_list)))
    return nodes


def identify_merge_commit_parents(commit_parents: List[List[str]]) -> List[List[str]]:
    """From the list of all commits and commit parents, find the merge commits and then return
    a list of parents of these merge commits.
    :param commit_parents: a list of commit parents corresponding to all commits.
    :returns: a list of merge commit parents, two parents for each merge commit.
    """
    merge_commit_parents = []
    for parents in commit_parents:
        if len(parents) > 1:
            merge_commit_parents.append(parents)
    return merge_commit_parents


def get_branch_commits(all_commits, commit_parents, merge_commit_parents):
    """After identifying the parents of merge commits, plot out each branch by following
    the commits back in time, taking the first parent if there is a choice of two commits.
    This is roughly equivalent to the git command:
    git log --reverse --first-parent --pretty=format:"%h" commit_id
    where commit_id is the child commit. of the two parents."""
    nodes = []
    for parent_pair in merge_commit_parents:
        for parent_id in parent_pair:
            child_index = commit_parents.index(parent_pair)
            child_id = all_commits[child_index]
            commit_list = [child_id, parent_id]
            parents = True
            while parents:
                if parent_id in all_commits:
                    parent_index = all_commits.index(parent_id)
                    parents = commit_parents[parent_index]
                    parent_id = parents[0]
                    commit_list.append(parent_id)
                else:
                    parents = False
            nodes.append(list(reversed(commit_list)))
    return nodes


def add_unmerged_branches(refs, all_commits, commit_parents, nodes):
    """Unmerged branches are not identified since they do not have a merge commit.
    Unmerged branches can't exist without a ref so we can find them by going through
    all of the refs."""
    flat_parents = [commit_id for sublist in commit_parents for commit_id in sublist]
    for branch_name in refs:
        if refs[branch_name] not in flat_parents:
            branch = [refs[branch_name]]
            if refs[branch_name] in all_commits:
                parent_index = all_commits.index(refs[branch_name])
                parents = commit_parents[parent_index]
                while parents:
                    parent_id = parents[0]
                    branch.append(parent_id)
                    if parent_id in all_commits:
                        parent_index = all_commits.index(parent_id)
                        parents = commit_parents[parent_index]
                    else:
                        parents = False
                nodes.append(list(reversed(branch)))
    return nodes


def output_dot_file(nodes, refs, all_commits):
    """Makes the output file from the collected information."""
    with open("output.dot", 'w') as output_file:
        output_nodes(nodes, output_file)
        output_refs(refs, output_file, all_commits)


def output_nodes(nodes: List[List], output_file: TextIO):
    """Output a representation of the commits.
    :param nodes: A list of commits in each branch of the repository.
    :param output_file: An open file handle to write to.
    """
    output_file.write("strict digraph example {\n")
    for branch_index, branch in enumerate(nodes):
        output_file.write(f'\tnode[group="{branch_index}"];\n\t')
        for commit_index, commit_id in enumerate(branch):
            output_file.write(f'"{commit_id}"')
            if commit_index < (len(branch) - 1):
                output_file.write(" -> ")
            else:
                output_file.write(";\n")
    output_file.write("\n")


def output_refs(refs: dict, output_file: TextIO, all_commits):
    """Output ref labels to decorate the nodes.
    :param refs: A dict of name: commit_id pairs describing repository refs.
    :param output_file: An open file handle to write to.
    """
    for ref_index, ref in enumerate(refs):
        if refs[ref] in all_commits:
            output_file.write(f'\tsubgraph Decorate{ref_index}\n\t{{\n')
            output_file.write('\t\trank = "same";\n')
            output_file.write(f'\t\t"({ref})" [shape = "box", style = "filled", '
                              f'fillcolor = "#ddddff"];\n')
            output_file.write(f'\t\t"({ref})" -> "{refs[ref]}" [weight = 0, arrowtype = "none", '
                              f'dirtype = "none", arrowhead = "none", style = "dotted"];\n\t}}\n')
    output_file.write("}\n")


def render():
    """Render the generated dot file"""
    subprocess.run('dot -Tpng -Gdpi=150 output.dot -o output.png')


def process_commits(all_commits: List[str], commit_parents: List[List[str]], refs: dict):
    """ Process commit data to produce a group of nodes and edges to be plotted by GraphVis.
    :param all_commits: A list of commit ids with most recent first,
    these are given by: git log --all --pretty=format:"%h"
    :param commit_parents: The parents of each commit in all commits.
     Given by: git log --all --pretty=format:"%p"
    :param refs: Given by: git for-each-ref --format="'%(refname:short)': '%(objectname:short),'".
    These are used for labelling but also to catch any branches which are unmerged.
    """
    merge_commit_parents = identify_merge_commit_parents(commit_parents)
    nodes = get_branch_commits(all_commits, commit_parents, merge_commit_parents)
    nodes = add_unmerged_branches(refs, all_commits, commit_parents, nodes)
    nodes = catch_empty_graph(nodes, all_commits, commit_parents)
    return nodes


def get_data_from_gitlab(gitlab_project, start_date: str,
                         end_date: str) -> Tuple[List[str], List[List[str]], dict]:
    """Fetch commit and ref data from GitLab matching the specified group and dates."""

    request_parameters = {'since': datetime.datetime.strptime(start_date, "%d/%m/%y").isoformat(),
                          'until': datetime.datetime.strptime(end_date, "%d/%m/%y").isoformat(),
                          'all': True}
    gitlab_commits = gitlab_project.commits.list(all=True, query_parameters=request_parameters)
    gitlab_branches = gitlab_project.branches.list(all=True)
    all_commits = []
    commit_parents = []
    refs = {}
    # The order of the commit IDs doesnt matter as long as the commit IDs
    # line up with the parent IDs.
    for commit in gitlab_commits:
        all_commits.append(commit.attributes["short_id"])
        parents = []
        for parent in commit.attributes["parent_ids"]:
            parents.append(parent[:8])
        commit_parents.append(parents)
    for branch in gitlab_branches:
        refs[branch.attributes["name"]] = branch.attributes["commit"]["short_id"]
    return all_commits, commit_parents, refs


def main():
    """Main entry point for commit graph plotting."""
    config_path = "../../../robota-marking/robota-config.yaml"
    start_date = "01/10/19"
    end_date = "17/10/19"
    team_name = "S1Team01"

    robota_config = get_robota_config(config_path, {"team_name": team_name})

    gitlab_repo = new_repository(robota_config)

    all_commits, commit_parents, refs = get_data_from_gitlab(gitlab_repo.gitlab_project,
                                                             start_date, end_date)
    events = gitlab_repo.get_events()

    # If any parent is empty then invent a fake parent.
    for index, parents in enumerate(commit_parents):
        if not parents:
            commit_parents[index] = ["None"]

    nodes = process_commits(all_commits, commit_parents, refs)

    output_dot_file(nodes, refs, all_commits)

    render()


if __name__ == '__main__':
    main()
