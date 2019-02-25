from jinja2 import Template, Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import UndefinedError
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from random import randint
from base64 import b64decode
from os import environ, path, makedirs
import yaml

def Build(args, pipeline_name, config, iteration, commit, kubeline_yaml, namespace):
    template_file = 'templates/job.jinja.yml'
    env = Environment(loader=FileSystemLoader('.'), undefined=StrictUndefined)
    template = env.get_template(template_file)

    build_spec = {
        'job_runner_image': args['--job-runner-image'],
        'pipeline_name': pipeline_name,
        'config': config,
        'iteration': iteration,
        'commit': commit,
        'stages': kubeline_yaml['stages'],
        'influxdb_host': args['--influxdb-host'],
        'influxdb_db': args['--influxdb-db']
    }
    body = template.render(build_spec)
    body = yaml.load(body)
    load_config()
    batch = client.BatchV1Api()
    if 'docker_secret' in config:
        secret, err = get_secret(config['docker_secret'], namespace,
            secret_type='kubernetes.io/dockerconfigjson')
        if err:
            return None, err
    resp = batch.create_namespaced_job(namespace, body)
    return resp, None

def get_secret(name, namespace, secret_type=None):
    load_config()
    core = client.CoreV1Api()
    try:
        resp = core.read_namespaced_secret(name, namespace)
    except ApiException:
        return None, f'could not locate secret {namespace}/{name}'
    if secret_type:
        if resp.type != secret_type:
            return None, f'secret {namespace}/{name} is not type {secret_type}'
    result = {}
    for key, value in resp.data.items():
        result[key] = b64decode(value).decode('utf-8')
    return result, None

def get_recent_job(pipeline, namespace):
    load_config()
    batch = client.BatchV1Api()
    labels = 'app=kubeline,pipeline={}'.format(pipeline)
    limit=20
    resp = batch.list_namespaced_job(namespace, label_selector=labels,
                                     limit=limit)
    if len(resp.items) == 0:
        return None
    results = [item for item in resp.items]
    while resp.metadata._continue:
        resp = batch.list_namespaced_job(namespace, label_selector=labels,
            limit=limit, _continue=resp.metadata._continue)
        for item in resp.items:
            results.append(item)
    return max(results, key=lambda r: r.status.start_time)

def validate_pipeline_spec(kubeline_yaml):
    if not (type(kubeline_yaml) is dict and 'stages' in kubeline_yaml):
        err = 'pipeline spec must be dict containing "stages" key'
        return None, err
    get_missing = lambda fields, stage: [f for f in fields if f not in stage]
    build_stages = []
    for stage in kubeline_yaml['stages']:
        msg = f'stage {stage["name"]} - '
        if 'name' not in stage:
            return None, 'all stages require name field'
        missing = get_missing(['name', 'type'], stage)
        if missing:
            err = msg + 'missing field(s) {missing}'
            return None, err
        valid_types = ['docker-build', 'docker-push']
        if stage['type'] not in valid_types:
            err = msg + 'type {stage["type"]} not valid'
            return None, err
        if stage['type'] == 'docker-build':
            build_stages.append(stage['name'])
            if 'build_dir' not in stage:
                stage['build_dir'] = '.'
            if 'dockerfile' not in stage:
                stage['dockerfile'] = 'Dockerfile'
        if stage['type'] == 'docker-push':
            missing = get_missing(['from_stage', 'repo', 'tags'], stage)
            if missing:
                err = msg + f'missing field(s) {missing}'
                return None, err
            if stage['from_stage'] not in build_stages:
                err = msg + f'from_stage stage["from_stage"] not found'
                return None, err
            if ':' in stage['repo']:
                err = msg + 'repo field may not contain tags'
                return None, err
    return kubeline_yaml, None

def get_namespace():
    namespace = None
    file_path = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
    if path.isfile(file_path):
        with open(file_path, 'r') as stream:
            namespace = stream.read()
    return namespace

def load_config():
    if path.isfile(environ['HOME'] + '/.kube/config'):
        config.load_kube_config()
    else:
        config.load_incluster_config()

