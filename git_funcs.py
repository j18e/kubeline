from git import Repo, cmd
from git.exc import GitCommandError
from random import randint
from requests import get
from shutil import rmtree
import os.path
import yaml

def get_commit_sha(url, branch):
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
        msg = 'ERROR fetching most recent commit sha for {} on branch {}'
        print(msg.format(url, branch))
        print(e)
        return None
    if len(refs) != 1:
        return None
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

def get_pipeline_config(url, commit_sha):
    path = clone_commit(url, commit_sha)
    full_path = path + '/kubeline.yml'
    if not path:
        return False
    if not os.path.isfile(full_path):
        msg = 'ERROR {} not found in {} at {}'
        print(msg.format(full_path.split('/')[-1], url, commit_sha))
        rmtree(path)
        return False
    with open(full_path, 'r') as stream:
        config = yaml.load(stream.read())
    rmtree(path)
    return config

