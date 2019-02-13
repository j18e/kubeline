#!/usr/bin/env python3

"""
Usage:
  main.py [options]
  main.py [options] dev

Options:
  -f                      specify config file [default: config.yml]
  -s                      specify state file  [default: state.yml]
  -h --help               show this help text

"""

from datetime import datetime, timedelta
from docopt import docopt
from k8s import Build
from os import environ
from time import sleep
import git
import yaml

def load_config(args):
    with open(args['-f'], 'r') as stream:
        config = yaml.load(stream.read())
    for name, pipeline in config['pipelines'].items():
        if not pipeline.get('branch'):
            pipeline['branch'] = 'master'
    return config

def get_state(args):
    try:
        with open(args['-s'], 'r') as stream:
            state = yaml.load(stream.read())
        print('loading state from {}...'.format(args['-s']))
    except FileNotFoundError:
        print('state file not at {}. Starting with empty state...'.format(
            args['-s']))
        state = {}
    return state

def put_state(args, state):
    with open(args['-s'], 'w') as output:
        yaml.dump(state, output, default_flow_style=False)
    return True

def get_repo(path, url, branch):
    repo = Repo.clone_from(url, path)
    head = list(repo.iter_commits(branch, max_count=1))[0]
    return head.hexsha

def get_head(repo, branch):
    origin = repo.remote()
    origin.pull()
    head = list(repo.iter_commits(branch, max_count=1))[0]
    return head.hexsha

def init(args):
    config = load_config(args)
    state = get_state(args)
    for name, pipeline in config['pipelines'].items():
        if not state.get(name):
            state[name] = {
                'git_ref': None,
                'iteration': 0,
                'last_checked': datetime.fromtimestamp(0),
                'last_run': datetime.fromtimestamp(0)
            }
            state[name]['git_ref'] = get_ref(pipeline['git_url'],
                                             pipeline['branch'])
    put_state(args, state)
    return config, state

def check_pipeline(args, name, pipeline, state):
    msg = 'successfully triggered pipeline {} at ref {}'
    git_ref = get_ref(pipeline['git_url'], pipeline['branch'])
    if git_ref == state['git_ref']:
        return None
    resp = Build(args, name, pipeline, iteration=state['iteration']+1,
                 git_ref=git_ref)
    if resp:
        print(msg.format(name, git_ref[:6]))
        state['iteration'] += 1
        state['git_ref'] = git_ref
        state['last_run'] = resp
        return state

def get_repo(path, url, branch):
    if not os.path.exists(path):
        clone = ['git', 'clone', url, path]
        get_hash = ['git', 'rev-parse', branch]
        p = Popen(clone, cwd=work_dir)
        p.wait()
        with open(path + '/kubeline.yml', 'r') as stream:
            pipeline_config = yaml.load(stream.read())
    return commit_hash, pipeline_config

def main(args):
    if args['dev']:
        msg = 'dev mode - using {} and {} for state and config'
        args['-f'] = './dev/config.yml'
        args['-s'] = './tmp/state.yml'
        print(msg.format(args['-f'], args['-s']))
    else:
        print('only dev mode currently available')
        exit()

    config, repos, state = init(args)
    check_frequency = timedelta(seconds=60)

    while True:
        for name, pipeline in config['pipelines'].items():
            put_state(args, state)
            if datetime.now() - state[name]['last_checked'] < check_frequency:
                continue
            print('checking', name)
            pipeline_state = check_pipeline(args, name,
                                            pipeline, state[name])
            state[name]['last_checked'] = datetime.now()
            if pipeline_state:
                state[name] = pipeline_state
            put_state(args, state)
        sleep(5)


if __name__ == '__main__':
    main(docopt(__doc__))

