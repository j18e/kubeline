#!/usr/bin/env python3

from influxdb import InfluxDBClient
from time import sleep
from os import environ

pipelines = {
    'weather-exporter': {
        'stages': 3,
        'jobs': [
            1,
            2
        ]
    },
    'slack-bot': {
        'stages': 2,
        'jobs': [
            1,
            None,
            None,
            0
        ]
    },
    'newapp': {
        'stages': 5,
        'jobs': [
            None,
            None,
            None,
            3,
            4
        ]
    }
}

def write_log(tags, line):
    body = {
        'measurement': 'job_logs',
        'tags': tags,
        'fields': {'value': line}
    }
    client.write_points([body])

def write_status(tags, code):
    if code == 1:
        status = 'running'
    elif code == -1:
        status = 'failed'
    elif code == 2:
        status = 'succeeded'
    body = {
        'measurement': 'job_status',
        'tags': tags,
        'fields': {'code': code, 'value': status}
    }
    client.write_points([body])

def run_job(tags, stage_count, fail_stage):
    stages = [str(n)+'-name' for n in range(stage_count)]
    write_status(tags, 1)
    for idx, stage in enumerate(stages):
        stage_tags = tags
        stage_tags['stage'] = stage
        print('running', stage)
        write_log(stage_tags, 'starting the things...')
        sleep(.1)
        write_log(stage_tags, 'doing the things...')
        sleep(.5)
        write_log(stage_tags, 'doing the things...')
        sleep(.3)
        write_log(stage_tags, 'still doing the things...')
        sleep(1)
        if idx == fail_stage:
            print('failing stage')
            write_log(stage_tags, 'oh no I FAILED!')
            write_status(tags, -1)
            return
        else:
            write_log(stage_tags, 'i FINISHED!')
            write_status(tags, 2)

host = environ['INFLUXDB_HOST']
database = environ['INFLUXDB_DATABASE']
client = InfluxDBClient(host=host, database=database)

for name, pipeline in pipelines.items():
    for idx, job in enumerate(pipeline['jobs']):
        tags = {'pipeline': name, 'job': name+'-'+str(idx+1)}
        print('job', tags['job'])
        run_job(tags, pipeline['stages'], job)

