from git import Repo, cmd
from git.exc import GitCommandError
from random import randint
from shutil import rmtree
from yaml import load
import os.path

def get_commit_sha(url, branch):
    client = cmd.Git()
    try:
        refs = client.ls_remote(url).split('\n')
        refs = [ref.split('\t')[0] for ref in refs
               if ref.split('\t')[1].split('/')[-1] == branch]
    except GitCommandError as e:
        msg = 'ERROR fetching most recent commit sha for {} on branch {}'
        print(msg.format(url, branch))
        print(e)
        return False
    if len(refs) != 1:
        return False
    return refs[0]

def clone_commit(url, commit_sha):
    repo_dir = str(randint(1000, 9999))
    path = 'tmp/repos/' + repo_dir
    try:
        repo = Repo.clone_from(url, path)
        head = repo.create_head(path, commit_sha)
        repo.head.reference = head
        repo.head.reset(index=True, working_tree=True)
    except:
        msg = 'ERROR cloning {} and checking out {}'
        print(msg.format(url, commit_sha))
        return False
    return path

def check_pipeline_config(config):
    return True

def get_pipeline_config(url, branch):
    commit_sha = get_commit_sha(url, branch)
    if not commit_sha:
        return False, False
    path = clone_commit(url, commit_sha)
    if not path:
        return False, False
    config_file = 'kubeline.yml'
    full_path = path + '/' + config_file
    if not os.path.isfile(full_path):
        msg = 'ERROR {} not found in {} on branch {}'
        print(msg.format(config_file, url, branch))
        rmtree(path)
        return False, commit_sha
    with open(full_path, 'r') as stream:
        config = load(stream.read())
    if not check_pipeline_config(config):
        rmtree(path)
        return False, commit_sha
    rmtree(path)
    return config, commit_sha

