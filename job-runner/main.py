#!/usr/bin/env python3

"""
Usage:
  main.py [options] --pipeline=<name> --job=<name> --stages=<names> --log-dir=<dir> --completion-string=<string> --failure-string=<string> --influxdb-host=<host>

Starting with the first provided stage name, Kfollow will provision a log file
named for the stage itself, in the --log-dir directory. Kfollow will tail the
log file until the --completion-string string is detected as the start of
a line. It will then assume the stage is complete, and move onto the next stage.

Options:
  --pipeline=<name>                     name of the pipeline (eg: myapp)
  --job=<name>                          name of the job (eg: myapp-1)
  --stages=<names>                      comma separated list of stage names
  --log-dir=<dir>                       directory to contain log files
  --completion-string=<string>          log line signaling stage completion
  --failure-string=<string>             log line signaling stage failure
  --influxdb-database=<name>            influxdb database to be written to [default: kubeline]
  --influxdb-host=<host>                hostname of influxdb server
  -h --help                             show this help text
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

def follow_file(client, tags, file_path, sig_finished, sig_failed, stage_success=None):
    with open(file_path, 'w') as stream:
        if stage_success is False:
            print('failing stage due to previous failure...')
            stream.write(sig_failed)
            return False
        stream.write('')

    sleep_time = 0.1
    line = ''

    client.write_points(format_metric('job_logs', tags, {'value': 'STARTING'}))
    with open(file_path, 'r') as stream:
        while not line.startswith(sig_finished):
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

def main(args):
    pipeline = args['--pipeline']
    job = args['--job']
    database = args['--influxdb-database']
    client = InfluxDBClient(host=args['--influxdb-host'], database=database)

    sig_finished = args['--completion-string']
    sig_failed = args['--failure-string']

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
        fields = {'value': 'waiting'}
        tags = {'pipeline': pipeline, 'job': job, 'stage': stage}
        client.write_points(format_metric('job_logs', tags, fields))
    for stage in stages:
        tags = {'pipeline': pipeline, 'job': job, 'stage': stage}
        log_file = '{}/{}'.format(args['--log-dir'], stage)
        print('starting', stage)
        stage_success = follow_file(client, tags, log_file, sig_finished, sig_failed, stage_success=stage_success)
    if stage_success is True:
        print('job completed successfully')
        status = format_metric('job_status', job_tags, job_fields['succeeded'])
    else:
        print('job ended with failure')
        status = format_metric('job_status', job_tags, job_fields['failed'])
    client.write_points(status)

if __name__ == '__main__':
    main(docopt(__doc__))

