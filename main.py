#!/usr/bin/env python3

"""
Usage:
  main.py [options] --config-file=<file> --influxdb-host=<name>

Options:
  --check-frequency=<seconds>       how often kubeline will check git repos [default: 60]
  --config-file=<file>              config file to use [default: config.yml]
  --http-port=<port>                http port on which to listen [default: 8080]
  --namespace=<namespace>           namespace in which to run jobs
  --influxdb-host=<name>            hostname of influxdb server
  --influxdb-db=<name>              name of the influxdb database to use [default: kubeline]
  --job-runner-image=<name>         image to pull for the job runner [default: j18e/job-runner:latest]
  --git-key-secret=<name>           k8s secret containing kubelines ssh key [default: kubeline-git-key]
  -h --help                         show this help text

"""

from datetime import datetime
from docopt import docopt
from flask import Flask
from git_funcs import get_pipeline_spec, get_commit, init_git_key
from k8s_funcs import Build, get_recent_job, get_namespace
from threading import Thread
from time import sleep
import yaml

app = Flask(__name__)

now = lambda : int(datetime.now().timestamp())

def load_pipelines(pipelines=None):
    global namespace
    print('initializing pipeline state...')

    with open(args['--config-file'], 'r') as stream:
        config_file = yaml.load(stream.read())
    config_file = config_file['pipelines']

    for name in config_file:
        if 'branch' not in config_file[name]:
            config_file[name]['branch'] = 'master'
    pipelines = {name: {'config': config_file[name], 'iteration': 0,
                 'commits': {}} for name in config_file}

    for name in pipelines:
        err = None
        job = get_recent_job(name, namespace)
        if job and 'iteration' in job.metadata.labels:
            pipelines[name]['iteration'] = int(job.metadata.labels['iteration'])
        if job and 'commit' in job.metadata.labels:
            commit = job.metadata.labels['commit']
        else:
            commit, err = get_commit(pipelines[name]['config'])
        if err:
            print(f'ERROR/init {name}: {err}')
            continue
        pipelines[name]['commits'][commit] = None
        pipeline_spec, _, err = get_pipeline_spec(pipelines[name]['config'],
            commit=commit)
        if err:
            print(f'ERROR/init {name}: {err}')
            continue
        pipelines[name]['commits'][commit] = pipeline_spec
    print('pipeline state successfully initialized')
    return pipelines

def commit_updater():
    global args
    global pipelines
    global queue
    global namespace
    check_frequency = int(args['--check-frequency'])
    print(f'checking repos every {check_frequency} seconds...')

    while True:
        print('CHECK for new commits...')
        start_time = now()
        for name in pipelines:
            commit, err = get_commit(pipelines[name]['config'])
            if err:
                pipelines[name]['check_error'] = True
                print(f'ERROR/check {name}: {err}')
                continue
            if commit in pipelines[name]['commits']:
                continue
            pipeline_spec, _, err = get_pipeline_spec(pipelines[name]['config'], commit=commit)
            if err:
                print(f'ERROR/check: pipeline spec in {name}')
                continue
            pipelines[name]['commits'][commit] = pipeline_spec
            print(f'ADD {name} to queue')
            queue.append((name, commit))
        time_elapsed = start_time - now()
        sleep(check_frequency - time_elapsed)

def queue_watcher():
    global args
    global pipelines
    global queue
    global namespace
    print('starting queue watcher...')

    while True:
        if not queue:
            sleep(1)
            continue
        job = queue.pop()
        name = job[0]
        commit = job[1]
        pipeline = pipelines[name]
        if not commit:
            commit, err = get_commit(pipeline['config'])
            if err:
                pipelines[name]['check_error'] = True
                print(f'ERROR getting commit for {name}: {err}')
                continue
        if commit in pipeline['commits']:
            pipeline_spec = pipeline['commits'][commit]
            if not pipeline_spec:
                print(f'ERROR/trigger {name} at {commit}: no pipeline spec')
                continue
        else:
            pipeline_spec, _, err = get_pipeline_spec(pipelines[name]['config'], commit=commit)
            pipelines[name][commit] = pipeline_spec
            if err:
                print(f'ERROR/trigger {name} at {commit}: {err}')
                continue
        resp, err = Build(args, name, pipeline['config'],
            pipeline['iteration']+1, commit, pipeline_spec, namespace)
        if err:
            print(f'ERROR/trigger {name}: {err}')
            continue
        print(f'TRIGGERED {name} at {commit}')
        pipelines[name]['iteration'] += 1


@app.errorhandler(404)
def not_found(error):
    return '404 not found\n', 404

@app.errorhandler(500)
def not_found(error):
    return '500 internal server error\n', 500

@app.route('/api/run/<pipeline>', methods=['POST'])
def trigger_build(pipeline):
    global queue
    global pipelines
    if pipeline not in pipelines:
        msg = f'ERROR pipeline "{pipeline}" not found\n'
        return msg, 404
    if pipelines[pipeline].get('check_error') is True:
        msg = f'ERROR git check error in {pipeline}'
        return msg, 500
    queue.append((pipeline, None))
    return f'{pipeline} added to queue'

if __name__ == '__main__':
    args = docopt(__doc__)
    namespace = args['--namespace'] or get_namespace() or 'default'
    _, err = init_git_key(args['--git-key-secret'], namespace)
    if err:
        print(f'ERROR/ssh: {err}. Exiting...')
        exit()
    pipelines = load_pipelines()
    queue = []
    commit_updater_thread = Thread(target=commit_updater)
    commit_updater_thread.start()
    queue_watcher_thread = Thread(target=queue_watcher)
    queue_watcher_thread.start()
    app.run(host='0.0.0.0', port=int(args['--http-port']))

