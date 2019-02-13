from git import Repo
from shutil import rmtree
import os.path

def Get_repo(path, url, branch):
    try:
        repo = Repo(path)
        repo.remote().url == url
    except:
        if os.path.exists(path):
            rmtree(path)
        repo = Repo.clone_from(url, path)
    if repo.active_branch.name != branch:
        repo = set_branch(repo, branch)
    repo = get_changes(repo, branch)
    commit = repo.head.commit.hexsha
    config = get_pipeline_config(path)
    return commit, config

def set_branch(repo, branch):
    if str(repo.active_branch) != branch:
        head = None
        for head_obj in repo.heads:
            if str(head_obj) == branch:
                head = head_obj
                repo.head.reference = head
                break
        if not head:
            print('branch not found in heads. Searching refs...')
            branch_ref = None
            for idx, ref in enumerate(repo.refs):
                if str(ref).split('/')[-1] == branch:
                    branch_ref = repo.refs[idx]
                    break
            if not branch_ref:
                print('branch {} not found'.format(branch))
            head = repo.create_head(branch, str(branch_ref))
        repo.head.reference = head
        repo.head.reset(index=True, working_tree=True)
    return repo

def get_changes(repo, branch):
    remote = repo.remote()
    resp = remote.pull(branch)
    return repo

def get_pipeline_config(path):
    path = path + '/kubeline.yml'
    if not os.path.isfile(path):
        return False
    with open(path, 'r') as stream:
        config = yaml.load(stream.read())
    return config

