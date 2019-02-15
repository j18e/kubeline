#!/usr/bin/env python3

"""
Usage:
  main.py [options]
  main.py [options] dev

Options:
  -f <file>               specify config file [default: config.yml]
  -s <file>               specify state file  [default: state.yml]
  -h --help               show this help text

"""

from datetime import datetime, timedelta
from docopt import docopt
from git_funcs import get_pipeline_config
from k8s import Build
from os import environ
from prometheus_client import start_http_server, Gauge
from time import sleep
import git
import sys
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
        if state is None:
            state = {}
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
    url = pipeline['git_url']
    branch = pipeline['branch']
    pipeline_config, commit_sha = get_pipeline_config(url, branch)
    if not commit_sha:
        state['config_healthy'] = False
        return state
    if not pipeline_config:
        state['config_healthy'] = False
        state['commit_sha'] = commit_sha
        return state
    state['config_healthy'] = True
    if not state.get('commit_sha'):
        state['commit_sha'] = commit_sha
        return state
    if commit_sha != state['commit_sha']:
        resp = Build(name, url, pipeline_config, commit_sha,
                     iteration=state['iteration']+1)
        if resp:
            msg = 'successfully triggered pipeline {} at ref {}'
            print(msg.format(name, commit_sha[:6]))
            state['iteration'] += 1
            state['commit_sha'] = commit_sha
            state['last_run'] = resp
    return state

def main(args):
    if args['dev']:
        pass
    else:
        print('only dev mode currently available')
        exit()

    config, state = init(args)
    check_frequency = timedelta(seconds=config['check_frequency'])
    msg = 'starting watcher with check frequency of {} seconds'
    print(msg.format(config['check_frequency']))

    metric_pipeline_config = Gauge(
        'kubeline_pipeline_config_healthy',
        'Whether a valid config was successfully fetched from a configured \
pipeline\'s remote and branch',
        ['pipeline']

    )
    start_http_server(8080)

    while True:
        for name, pipeline in config['pipelines'].items():
            put_state(args, state)
            if datetime.now() - state[name]['last_checked'] < check_frequency:
                continue
            print('checking', name)
            pipeline_state = check_pipeline(args, name, pipeline, state[name])
            state[name]['last_checked'] = datetime.now()
            pipeline_state['last_checked'] = datetime.now()
            if pipeline_state['config_healthy']:
                metric_pipeline_config.labels(name).set(1)
            else:
                metric_pipeline_config.labels(name).set(0)
            put_state(args, state)

        sleep(5)

if __name__ == '__main__':
    main(docopt(__doc__))

