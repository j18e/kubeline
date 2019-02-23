#!/usr/bin/env python3

"""
Usage:
  main.py [options] --config-file=<file> --influxdb-host=<name>

Options:
  --config-file=<file>              config file to use [default: config.yml]
  --http-mode                       enable http mode
  --http-port=<port>                http port on which to listen [default: 8080]
  --namespace=<namespace>           namespace in which to run jobs
  --influxdb-host=<name>            hostname of influxdb server
  --influxdb-db=<name>              name of the influxdb database to use [default: kubeline]
  --job-runner-image=<name>         image to pull for the job runner [default: j18e/job-runner:latest]
  --git-key-secret=<name>           name of the kubernetes secret containing the ssh key for cloning repositories [default: kubeline-git-key]
  -h --help                         show this help text

"""

from datetime import datetime
from docopt import docopt
from git_funcs import get_kubeline_yaml, get_commit
from k8s import Build, get_recent_job, validate_spec, get_namespace
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

def check_pipeline(name, config, namespace, commit=None):
    url = config['git_url']
    branch = config['branch']
    if not commit:
        job = get_recent_job(name, namespace)
        if job:
            commit = job.metadata.labels.get('commit')
        else:
            return get_commit(url, branch)
    print('CHECK {} for commit newer than {}'.format(name, commit[:6]))
    new_commit = get_commit(url, branch)
    if not new_commit:
        return commit
    if new_commit == commit:
        return commit
    kubeline_yaml = get_kubeline_yaml(config, commit=new_commit)
    kubeline_yaml = validate_spec(kubeline_yaml)
    if not kubeline_yaml:
        return new_commit,
    return new_commit, kubeline_yaml

def trigger_pipeline(name, config, iteration, commit, kubeline_yaml, namespace):
    if not commit:
        commit = config['branch']
    print('BUILD {} at {}...'.format(name, new_commit[:6]))
    resp = Build(args, name, config, iteration, commit, kubeline_yaml, namespace)
    if not resp:
        print('ERROR triggering {}'.format(name))
        return False
    print('successfully triggered {}'.format(name))
    return True

def main(args):
    check_frequency, pipelines = load_config(args)
    namespace = args['--namespace'] or get_namespace() or 'default'

    iterations = {name: 0 for name in pipelines}
    for name in pipelines:
        recent_job = get_recent_job(name, namespace)
        if recent_job:
            if recent_job.metadata.labels.get('iteration'):
                iterations[name] = int(recent_job.metadata.labels.get('iteration'))

    if args['--http-mode']:
        from flask import Flask
        http_app = Flask('kubeline')

        @http_app.errorhandler(404)
        def not_found(error):
            return '404 not found\n', 404

        @http_app.errorhandler(500)
        def not_found(error):
            return '500 internal server error\n', 500

        @http_app.route('/api/build/<pipeline>', methods=['POST'])
        def trigger_build(pipeline):
            if pipeline not in pipelines:
                msg = 'ERROR - pipeline "{}" not found\n'.format(pipeline)
                return msg, 404
            config = pipelines[pipeline]
            kubeline_yaml, commit = get_kubeline_yaml(config)
            if not commit:
                return 'ERROR getting git repo\n', 500
            if not kubeline_yaml:
                return 'ERROR getting kubeline yaml file\n', 500
            kubeline_yaml = validate_spec(kubeline_yaml)
            if not kubeline_yaml:
                return 'ERROR validating kubeline yaml file\n', 500
            resp = Build(args, pipeline, pipelines[pipeline], iterations[pipeline]+1, commit, kubeline_yaml, namespace)
            if not resp:
                return 'ERROR triggering the job\n', 500
            iterations[pipeline] += 1
            return 'job triggered'

        http_app.run(host='0.0.0.0', port=int(args['--http-port']))
        print('exiting...')
        return

    check_msg = 'checking repos/config every {} seconds'
    print(check_msg.format(check_frequency))

    commits = {name: None for name in pipelines}

    last_check = 0
    while True:
        if now() - last_check > check_frequency:
            new_check_frequency, new_pipelines = load_config(args)
            if new_pipelines != pipelines:
                print('LOAD new config...')
                pipelines = new_pipelines
            for name in pipelines:
                commits[name] = check_pipeline(name, pipelines[name],
                    namespace, commit=commits.get(name))
            last_check = now()
        sleep(1)

if __name__ == '__main__':
    main(docopt(__doc__))

