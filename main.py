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

def init(args):
    config = load_config(args)
    state = get_state(args)
    for name, pipeline in config['pipelines'].items():
        if not state.get(name):
            state[name] = {
                'iteration': 0,
                'last_checked': datetime.fromtimestamp(0),
                'last_run': datetime.fromtimestamp(0)
            }
    put_state(args, state)
    return config, state

def check_pipeline(args, name, pipeline, state):
    msg = 'successfully triggered pipeline {} at ref {}'
    if not state.get(path):
        path = args['--repo-dir'] + name
    path = state['path']
    url = pipeline['git_url']
    branch = pipeline['branch']
    git_commit, config = Get_repo(path, url, branch)
    if not state.get('git_commit'):
        state['git_commit'] = git_commit
        return state
    elif git_commit != state['git_commit']:
        resp = Build(args, name, pipeline, iteration=state['iteration']+1,
                     git_commit=git_commit)
    if resp:
        print(msg.format(name, git_commit[:6]))
        state['iteration'] += 1
        state['git_commit'] = git_commit
        state['last_run'] = resp
        return state

def main(args):
    if args['dev']:
        msg = 'dev mode - using {} and {} for state and config'
        args['-f'] = './dev/config.yml'
        args['-s'] = './tmp/state.yml'
        print(msg.format(args['-f'], args['-s']))
    else:
        print('only dev mode currently available')
        exit()

    config, state = init(args)
    check_frequency = timedelta(seconds=60)

    while True:
        for name, pipeline in config['pipelines'].items():
            put_state(args, state)
            if datetime.now() - state[name]['last_checked'] < check_frequency:
                continue
            print('checking', name)
            pipeline_state = check_pipeline(args, name, pipeline, state[name])
            state[name]['last_checked'] = datetime.now()
            pipeline_state['last_checked'] = datetime.now()
            state[name] = pipeline_state
            put_state(args, state)

        sleep(5)


if __name__ == '__main__':
    main(docopt(__doc__))

