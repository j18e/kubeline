from git import Repo, cmd
from git.exc import GitCommandError
from k8s_funcs import validate_pipeline_spec, get_secret
from os import environ, makedirs, chmod
import os.path
from random import randint
from requests import get
from requests.exceptions import HTTPError
from shutil import rmtree
import stat
import yaml

git_key_dir = './tmp/keys'
git_key_path = f'{git_key_dir}/id_rsa'
ssh_cmd = f'ssh -o StrictHostKeyChecking=no -i {git_key_path}'

def check_http_auth(url):
    if not url.startswith('https://'):
        return True, None
    try:
        resp = get(url)
        resp.raise_for_status()
        return True, None
    except HTTPError:
        return False, f'{url} does not exist or requires auth'

def get_commit(config):
    http_check, err = check_http_auth(config['git_url'])
    if err:
        return False, err
    url = config['git_url']
    branch = config['branch']
    client = cmd.Git()
    try:
        with client.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
            refs = client.ls_remote(url).split('\n')
        refs = [ref.split('\t')[0] for ref in refs
               if ref.split('\t')[1].split('/')[-1] == branch]
    except GitCommandError as err:
        return False, err
    if len(refs) != 1:
        return False, f'no commits found in branch {config["branch"]}'
    return refs[0], None

def clone_repo(url, git_ref, is_branch=False):
    msg = f'{url} at {git_ref}'
    if not check_http_auth(url):
        return False, False, f'{msg}: cannot clone authenticated http repos'
    repo_dir = str(randint(1000, 9999))
    repo_path = 'tmp/repos/' + repo_dir
    try:
        repo = Repo.clone_from(url, repo_path, env={'GIT_SSH_COMMAND': ssh_cmd})
        if is_branch:
            if repo.active_branch == git_ref:
                return repo_path, repo.head.commit.hexsha, None
            ref_names = [ref.name.split('/')[-1] for ref in repo.refs]
            git_ref = repo.refs[ref_names.index(git_ref)]
        head = repo.create_head(repo_path, git_ref)
        repo.head.reference = head
        repo.head.reset(index=True, working_tree=True)
    except GitCommandError as e:
        return None, None, f'{msg}: {e}'
    except ValueError as e:
        return None, None, f'{msg}: {e}'
    return repo_path, repo.head.commit.hexsha, None

def get_pipeline_spec(config, commit=None):
    file_name = 'kubeline.yml'
    url = config['git_url']
    if commit:
        repo_path, commit, err = clone_repo(url, commit)
    else:
        repo_path, commit, err = clone_repo(url, config['branch'], is_branch=True)
    if err:
        return None, None, err
    path = f'{repo_path}/{file_name}'
    if not os.path.isfile(path):
        rmtree(repo_path)
        return None, commit, f'did not find {file_name} in {url}'
    with open(path, 'r') as stream:
        config = yaml.load(stream.read())
    rmtree(repo_path)
    config, err = validate_pipeline_spec(config)
    if err:
        return None, commit, err
    return config, commit, None

def init_git_key(name, namespace):
    print(f'getting ssh keys from k8s secret {namespace}/{name}...')
    git_keys, err = get_secret(name, namespace)
    if err:
        return None, err
    if 'id_rsa' not in git_keys:
        return None, 'id_rsa not found in secret {namespace}/{name}'
    if not os.path.exists(git_key_dir):
        makedirs(git_key_dir)
        chmod(git_key_dir, stat.S_IRWXU)
    with open(git_key_path, 'w') as stream:
        stream.write(git_keys['id_rsa'])
    chmod(git_key_path, stat.S_IREAD)
    if 'id_rsa.pub' in git_keys:
        print('public key to add to your git repos: ' +
              git_keys['id_rsa.pub'].strip())
    return True, None

