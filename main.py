#!/usr/bin/env python3

"""
Usage:
  main.py [options] --config-file=<file>

Options:
  --configmap=<name>                configmap from which to load config
  --config-file=<file>              config file to use [default: config.yml]
  -h --help                         show this help text

"""

from datetime import datetime
from docopt import docopt
from git_funcs import get_kubeline_yaml, get_commit
from k8s import Build, check_secret, get_recent_job
from prometheus_client import start_http_server, Gauge
from time import sleep
import yaml

now = lambda : int(datetime.now().timestamp())

def load_config(args):
    with open(args['--config-file'], 'r') as stream:
        config = yaml.load(stream.read())
    for name in config['pipelines']:
        config['pipelines'][name]['branch'] = config[
            'pipelines'][name].get('branch') or 'master'
    return config['check_frequency'], config['pipelines']

def check_pipeline(name, config, commit, metrics):
    url = config['git_url']
    branch = config['branch']
    if not commit:
        job = get_recent_job(name)
        if job:
            commit = job.metadata.labels.get('commit')
        else:
            return get_commit(url, branch)
    print('CHECK {} for commit newer than {}'.format(name, commit[:6]))
    new_commit = get_commit(url, branch)
    if not new_commit:
        return commit
    metrics['check_error'].labels(name).set(False)
    if new_commit == commit:
        return commit
    kubeline_yaml = get_kubeline_yaml(url, new_commit)
    if not kubeline_yaml or not check_secret(config):
        metrics['config_error'].labels(name).set(True)
        return new_commit
    metrics['config_error'].labels(name).set(False)
    print('BUILD {} at {}...'.format(name, new_commit[:6]))

    resp = Build(name, config, new_commit, kubeline_yaml)
    if not resp:
        metrics['run_error'].labels(name).set(True)
        print('ERROR triggering {}'.format(name))
        return new_commit
    print('successfully triggered {}'.format(name))
    metrics['run_error'].labels(name).set(False)
    return new_commit

def main(args):
    labels = ['pipeline']
    metrics = {
        'check_error': Gauge('kubeline_check_error',
            'error checking git', labels),
        'config_error': Gauge('kubeline_config_error',
            'error in kubeline.yml or imagePullSecret', labels),
        'run_error': Gauge('kubeline_run_error',
            'error triggering build', labels)
    }
    start_http_server(8080)

    check_frequency, pipelines = load_config(args)

    check_msg = 'checking repos/config every {} seconds'
    print(check_msg.format(check_frequency))

    commits = {name: None for name in pipelines}

    last_check = 0
    while True:
        if now() - last_check > check_frequency:
            new_check_frequency, new_pipelines = load_config(args)
            if new_pipelines != pipelines:
                print('loading new config...')
                pipelines = new_pipelines
            for name in pipelines:
                commits[name] = check_pipeline(name, pipelines[name],
                    commits[name], metrics)
                if not commits[name]:
                    metrics['check_error'].labels(name).set(True)
            last_check = now()
        sleep(1)

if __name__ == '__main__':
    main(docopt(__doc__))

