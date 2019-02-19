#!/usr/bin/env python3

"""
Usage:
  main.py [options] --config-file=<file> --state-file=<file>

Options:
  --configmap=<name>                configmap from which to load config
  --config-file=<file>              config file to use [default: config.yml]
  --state-file=<file>               state file to use [default: state.yml]
  -h --help                         show this help text

"""

from datetime import datetime, timedelta
from docopt import docopt
from git_funcs import get_pipeline_config, get_commit_sha
from k8s import Build, get_configmap_data
from os import environ
from prometheus_client import start_http_server, Gauge
from time import sleep
import git
import sys
import yaml
import os.path

now = lambda : int(datetime.now().timestamp())
noalias_dumper = yaml.dumper.SafeDumper
noalias_dumper.ignore_aliases = lambda self, data: True

def load_config(args):
    with open(args['--config-file'], 'r') as stream:
        config = yaml.load(stream.read())
    for name, pipeline in config['pipelines'].items():
        if not pipeline.get('branch'):
            pipeline['branch'] = 'master'
    return config

def put_state(args, state):
    with open(args['--state-file'], 'w') as output:
        output.write(yaml.dump(state, default_flow_style=False, Dumper=noalias_dumper))
    return True

def check_pipeline(name, config, pipeline_state):
    commit_sha = get_commit_sha(config['git_url'], config['branch'])
    if not commit_sha:
        pipeline_state['check_error'] = True
        return pipeline_state
    pipeline_state['check_error'] = False
    if commit_sha == pipeline_state['commit_sha']:
        return pipeline_state
    pipeline_state['commit_sha'] == commit_sha
    pipeline = get_pipeline_config(config['git_url'], commit_sha)
    if not pipeline:
        pipeline_state['config_error'] = True
        return pipeline_state
    pipeline_state['config_error'] = False
    msg = 'triggering {} at {} on {}...'
    print(msg.format(name, commit_sha, config['branch']))
    build_spec = {
        'pipeline_name': name,
        'stages': pipeline['stages'],
        'iteration': pipeline_state['iteration']+1,
        'git': {
            'url': config['git_url'],
            'branch': config['branch'],
            'commit_sha': commit_sha,
        },
    }
    resp = Build(build_spec)
    msg = 'successfully triggered pipeline {} at ref {}'
    print(msg.format(name, commit_sha[:6]))
    pipeline_state['iteration'] += 1
    pipeline_state['last_run'] = resp.metadata.creation_timestamp.timestamp()
    return pipeline_state

def init_state(args, config):
    defaults = {'iteration': 0,
                'commit_sha': None}

    if os.path.isfile(args['--state-file']):
        with open(args['--state-file']) as stream:
            result = yaml.load(stream.read())
    else:
        print('starting with new state file...')
        result = {}

    for name in config['pipelines']:
        if name not in result:
            result[name] = defaults
    for name in result:
        if name not in config['pipelines']:
            del(result[name])
            continue
        if not result[name]['commit_sha']:
            result[name]['commit_sha'] = get_commit_sha(
                config['pipelines'][name]['git_url'],
                config['pipelines'][name]['branch']
            )
    return result

def init_metrics(pipelines, state, metrics=None):
    if not metrics:
        metrics = {
            'iteration': Gauge('kubeline_iteration',
                               'iteration of a configured pipeline',
                               ['pipeline']),
            'check_error': Gauge('kubeline_check_error',
                                 'error checking the git repo for new versions',
                                 ['pipeline']),
            'config_error': Gauge('kubeline_config_error',
                                  'improperly formatted kubeline.yml file',
                                  ['pipeline']),
            'last_run': Gauge('kubeline_last_run',
                              'pipeline\'s most recent run time',
                              ['pipeline'])
        }
        return metrics
    for metric in metrics:
        samples = metrics[metric].collect()[0].samples
        labels = [s[1]['pipeline'] for s in samples]
        for label in labels:
            if label not in pipelines:
                metrics[metric].remove(label)
    return metrics

def main(args):
    config = load_config(args)
    check_frequency = config['check_frequency']

    state = init_state(args, config)
    put_state(args, state)

    msg = 'starting watcher with check frequency of {} seconds'
    print(msg.format(config['check_frequency']))

    metrics = init_metrics([p for p in config['pipelines']], state)
    start_http_server(8080)

    last_check = 0
    while True:
        if now() - last_check > check_frequency:
            new_config = load_config(args)
            if new_config != config:
                print('loading new config...')
                config = new_config
                state = init_state(args, config)
                put_state(args, state)
                metrics = init_metrics([p for p in config['pipelines']], state, metrics=metrics)
            for name in config['pipelines']:
                print('checking', name)
                state[name] = check_pipeline(name, config['pipelines'][name], state[name])
                metrics['iteration'].labels(name).set(state[name]['iteration'])
                metrics['check_error'].labels(name).set(state[name].get('check_error') or False)
                metrics['config_error'].labels(name).set(state[name].get('config_error') or False)
                metrics['last_run'].labels(name).set(state[name].get('last_run') or False)
            put_state(args, state)
        sleep(1)

if __name__ == '__main__':
    main(docopt(__doc__))

