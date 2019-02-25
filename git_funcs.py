from git import Repo, cmd
from git.exc import GitCommandError
from k8s_funcs import validate_pipeline_spec, get_secret
from os import path, environ, makedirs, chmod
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
        return True
    try:
        resp = get(url)
        resp.raise_for_status()
        return True
    except HTTPError:
        print(f'ERROR {url} does not exist or requires auth')
        return False

def get_commit(config):
    if not check_http_auth(config['git_url']):
        return None
    url = config['git_url']
    branch = config['branch']
    client = cmd.Git()
    try:
        with client.custom_environment(GIT_SSH_COMMAND=ssh_cmd):
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
    if not check_http_auth(url):
        return False, False
    repo_dir = str(randint(1000, 9999))
    repo_path = 'tmp/repos/' + repo_dir
    try:
        repo = Repo.clone_from(url, repo_path, env={'GIT_SSH_COMMAND': ssh_cmd})
        if is_branch:
            if repo.active_branch == git_ref:
                return repo_path, repo.head.commit.hexsha
            ref_names = [ref.name.split('/')[-1] for ref in repo.refs]
            git_ref = repo.refs[ref_names.index(git_ref)]
        head = repo.create_head(repo_path, git_ref)
        repo.head.reference = head
        repo.head.reset(index=True, working_tree=True)
    except GitCommandError as e:
        print(f'ERROR cloning {url} and checking out {git_ref} {e}')
        return False, False
    return repo_path, repo.head.commit.hexsha

def get_pipeline_spec(config, commit=None):
    msg = f'ERROR getting pipeline spec from {config["git_url"]}'
    url = config['git_url']
    if commit:
        repo_path, commit = clone_repo(url, commit)
    else:
        repo_path, commit = clone_repo(url, config['branch'], is_branch=True)
    if not repo_path:
        print(msg)
        return False, False
    full_path = repo_path + '/kubeline.yml'
    if not path.isfile(full_path):
        msg = 'ERROR {} not found in {} at {}'
        print(msg.format(full_path.split('/')[-1], url, commit))
        rmtree(repo_path)
        return False, False
    with open(full_path, 'r') as stream:
        config = yaml.load(stream.read())
    rmtree(repo_path)
    config = validate_pipeline_spec(config)
    if not config:
        print(msg)
        return False, False
    return config, commit

def init_git_key(name, namespace):
    print(f'getting ssh keys from k8s secret {namespace}/{name}...')
    git_keys = get_secret(name, namespace)
    if not git_keys or 'id_rsa' not in git_keys:
        print(f'ERROR getting keys at {namespace}/{name}')
        return False
    if not path.exists(git_key_dir):
        makedirs(git_key_dir)
        chmod(git_key_dir, stat.S_IRWXU)
    print('writing key', git_key_path)
    with open(git_key_path, 'w') as stream:
        stream.write(git_keys['id_rsa'])
    chmod(git_key_path, stat.S_IREAD)
    if 'id_rsa.pub' in git_keys:
        print('public key we\'ll be using:')
        print(git_keys['id_rsa.pub'])
    return True

