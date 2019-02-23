from git import Repo, cmd
from git.exc import GitCommandError
from random import randint
from requests import get
from requests.exceptions import HTTPError
from shutil import rmtree
import os.path
import yaml

def get_commit(url, branch):
    client = cmd.Git()
    if url.startswith('https://'):
        try:
            resp = get(url)
            resp.raise_for_status()
        except HTTPError:
            msg = 'ERROR - {} does not exist or requires auth'
            print(msg.format(url))
            return None
    try:
        refs = client.ls_remote(url).split('\n')
        refs = [ref.split('\t')[0] for ref in refs
               if ref.split('\t')[1].split('/')[-1] == branch]
    except GitCommandError as e:
        msg = 'ERROR fetching most recent commit for {} on branch {}'
        print(msg.format(url, branch))
        print(e)
        return None
    if len(refs) != 1:
        return None
    return refs[0]

def clone_repo(url, git_ref, is_branch=False):
    repo_dir = str(randint(1000, 9999))
    path = 'tmp/repos/' + repo_dir
    try:
        repo = Repo.clone_from(url, path)
        if is_branch:
            if repo.active_branch == git_ref:
                return path
            ref_names = [ref.name.split('/')[-1] for ref in repo.refs]
            git_ref = repo.refs[ref_names.index(git_ref)]
        head = repo.create_head(path, git_ref)
        repo.head.reference = head
        repo.head.reset(index=True, working_tree=True)
    except:
        msg = 'ERROR cloning {} and checking out {}'
        print(msg.format(url, git_ref))
        return False
    return path, repo.head.commit.hexsha

def get_kubeline_yaml(config, commit=None):
    url = config['git_url']
    if commit:
        path, commit = clone_repo(url, commit)
    else:
        path, commit = clone_repo(url, config['branch'])
    full_path = path + '/kubeline.yml'
    if not path:
        return False
    if not os.path.isfile(full_path):
        msg = 'ERROR {} not found in {} at {}'
        print(msg.format(full_path.split('/')[-1], url, commit))
        rmtree(path)
        return False
    with open(full_path, 'r') as stream:
        config = yaml.load(stream.read())
    rmtree(path)
    return config, commit

