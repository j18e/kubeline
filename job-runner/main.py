#!/usr/bin/env python3

"""
Usage: main.py [options] PIPELINE (--stages=<names>) (--log-dir=<dir>)
           (--start=<string>) (--success=<string>) (--failure=<string>)
           (--influxdb-host=<host>) (--influxdb-db=<name>)

Starting with the first provided stage name, Kfollow will provision a log file
named for the stage itself, in the --log-dir directory. Kfollow will tail the
log file until the --finish-string string is detected as the start of a line.
It will then assume the stage is complete, and move onto the next stage.

Options:
  -h --help                             show this help text
  --stages=<names>                      comma separated list of stage names
  --start=<string>                      string to signal stage start
  --success=<string>                    string to signal stage success
  --failure=<string>                    string to signal stage failure
  --influxdb-db=<name>                  influxdb database to be written to
  --influxdb-host=<host>                hostname of influxdb server
  --time-limit=<seconds>                number of seconds before timing out job
  --log-dir=<dir>                       directory to write/read logs
  --env-vars-file=<file>                file inside log-dir to write env vars to
"""

from datetime import datetime
from docopt import docopt
from influxdb import InfluxDBClient
from os import environ, remove
from os.path import isfile
from pathlib import Path
from time import sleep
from math import ceil
from time import sleep
from requests.exceptions import ConnectionError

format_metric = lambda metric, tags, fields: [{'measurement': metric,
    'tags': tags, 'fields': fields}]

now = lambda : datetime.now().timestamp()

def get_iteration(client, pipeline):
    query = f'select last("value"),iteration from "job_status" where \
            "pipeline" = \'{pipeline}\''
    resp = client.query(query)
    if not resp:
        return 1
    iteration = list(resp.items()[0][1])[0]['iteration']
    if not iteration:
        return 1
    return int(iteration) + 1

def wait_for_db(client):
    influxdb_up = False
    query = 'select * from "empty"'
    while not influxdb_up:
        try:
            client.query(query)
            influxdb_up = True
        except ConnectionError:
            print('wating for influxdb to become available...')
            sleep(1)

def follow_file(client, tags, file_path, stage_success=None):
    sig_start = args['--start']
    sig_success = args['--success']
    sig_failed = args['--failure']
    with open(file_path, 'w') as stream:
        if stage_success is False:
            print('failing stage due to previous failure...')
            stream.write(sig_failed)
            return False
        stream.write('')

    sleep_time = 0.01
    line = ''

    client.write_points(format_metric('job_logs', tags, {'value': sig_start}))
    with open(file_path, 'r') as stream:
        while not line.startswith(sig_success):
            line = stream.readline().rstrip()
            if not line:
                continue
            client.write_points(format_metric('job_logs', tags, {'value': line}))
            print(line)
            if line.startswith(sig_failed):
                print('FAILURE FOUND IN', file_path)
                return False
            sleep(sleep_time)
    return True

def write_env_vars(file_path, env_vars):
    contents = ''
    for key, value in env_vars.items():
        contents += f'export {key.upper()}={str(value)}\n'
    with open(file_path, 'w') as stream:
        stream.write(contents)

def main():
    time_limit = int(args['--time-limit'])
    idb_host = args['--influxdb-host']
    database = args['--influxdb-db']
    pipeline = args['PIPELINE']
    log_dir = args['--log-dir']
    stages = args['--stages'].split(',')
    stages.sort()
    stage_success = None

    client = InfluxDBClient(host=idb_host, database=database)
    wait_for_db(client)

    iteration = get_iteration(client, pipeline)
    fields = {
        'pending': {'value': -1, 'description': 'pending'},
        'failure': {'value':-2,'description':'failure'},
        'running': {'value':0,'description':'running'},
        'success': {'value':1,'description':'success'},
        'duration': {'value': None, 'description': 'seconds'}
    }
    job = f'{pipeline}-{iteration}'

    env_vars_file = args['--env-vars-file']
    env_vars_file = f'{log_dir}/{env_vars_file}'
    env_vars = {
        'kubeline_iteration': iteration,
    }
    write_env_vars(env_vars_file, env_vars)

    print(f'starting job {job}')
    job_start_time = now()

    job_tags = {'pipeline': pipeline, 'job': job, 'iteration': iteration}
    stage_tags = job_tags

    status = format_metric('job_status', job_tags, fields['running'])
    client.write_points(status)

    for stage in stages:
        stage_tags['stage'] = stage
        client.write_points(format_metric('stage_duration', stage_tags,
                                          fields['pending']))

    for stage in stages:
        print('starting', stage)
        stage_tags['stage'] = stage
        log_file = '{}/{}'.format(log_dir, stage)
        stage_start_time = now()
        metric = format_metric('stage_duration', stage_tags, fields['running'])
        client.write_points(metric)
        stage_success = follow_file(client, stage_tags, log_file,
                                    stage_success=stage_success)
        print(stage_success)
        if stage_success:
            print('writing stage success')
            fields['duration']['value'] = ceil(now() - stage_start_time)
            metric = format_metric('stage_duration', stage_tags,
                                   fields['duration'])
            client.write_points(metric)
        else:
            print('writing stage failure')
            metric = format_metric('stage_duration', stage_tags,
                                   fields['failure'])
            client.write_points(metric)

    if stage_success is True:
        print('job completed successfully')
        status = format_metric('job_status', job_tags, fields['success'])
    else:
        print('job ended with failure')
        status = format_metric('job_status', job_tags, fields['failure'])
    client.write_points(status)

if __name__ == '__main__':
    args = docopt(__doc__)
    main()

