#!/usr/bin/env python3

"""
Usage: main.py [options]
           --pipeline=<name> --job=<name>
           --stages=<names> --log-dir=<dir>
           --start-string=<string>
           --success-string=<string>
           --failure-string=<string>
           --influxdb-host=<host>
           --influxdb-db=<name>

Starting with the first provided stage name, Kfollow will provision a log file
named for the stage itself, in the --log-dir directory. Kfollow will tail the
log file until the --finish-string string is detected as the start of a line.
It will then assume the stage is complete, and move onto the next stage.

Options:
  -h --help                             show this help text
  --pipeline=<name>                     name of the pipeline (eg: myapp)
  --job=<name>                          name of the job (eg: myapp-1)
  --stages=<names>                      comma separated list of stage names
  --influxdb-db=<name>                  influxdb database to be written to
  --influxdb-host=<host>                hostname of influxdb server
"""

from datetime import datetime
from docopt import docopt
from influxdb import InfluxDBClient
from os import environ, remove
from os.path import isfile
from pathlib import Path
from time import sleep

format_metric = lambda metric, tags, fields: [{'measurement': metric,
    'tags': tags, 'fields': fields}]

def follow_file(client, tags, file_path, stage_success=None):
    sig_start = args['--start-string']
    sig_success = args['--success-string']
    sig_failed = args['--failure-string']
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
                fields = {'value': 'failed', 'code': -1}
                client.write_points(format_metric('job_status', tags, fields))
                print('FAILURE FOUND IN', file_path)
                return False
            sleep(sleep_time)
    return True

def main():
    idb_host = args['--influxdb-host']
    database = args['--influxdb-db']
    pipeline = args['--pipeline']
    job = args['--job']
    log_dir = args['--log-dir']
    client = InfluxDBClient(host=idb_host, database=database)

    stages = args['--stages'].split(',')
    stages.sort()
    stage_success = None

    job_fields = {
        'failed': {'code':-1,'value':'failed'},
        'running': {'code':1,'value':'running'},
        'succeeded': {'code':2,'value':'succeeded'}
    }
    job_tags = {'pipeline': pipeline, 'job': job}
    status = format_metric('job_status', job_tags, job_fields['running'])
    client.write_points(status)

    for stage in stages:
        tags = {'pipeline': pipeline, 'job': job, 'stage': stage}
        log_file = '{}/{}'.format(log_dir, stage)
        print('starting', stage)
        stage_success = follow_file(client, tags, log_file, stage_success=stage_success)
    if stage_success is True:
        print('job completed successfully')
        status = format_metric('job_status', job_tags, job_fields['succeeded'])
    else:
        print('job ended with failure')
        status = format_metric('job_status', job_tags, job_fields['failed'])
    client.write_points(status)

if __name__ == '__main__':
    args = docopt(__doc__)
    main()

