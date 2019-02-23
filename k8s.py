from jinja2 import Template, Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import UndefinedError
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from random import randint
from os import environ, path
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
        if not check_secret(config['docker_secret'], namespace):
            return False
    resp = batch.create_namespaced_job(namespace, body)
    return resp

def check_secret(name, namespace):
    core = client.CoreV1Api()
    secret_type = 'kubernetes.io/dockerconfigjson'
    msg = 'ERROR getting secret {} in namespace {} - '.format(name, namespace)
    try:
        resp = core.read_namespaced_secret(name, namespace)
        assert resp.type == secret_type
    except ApiException:
        print(msg + 'could not locate secret')
        return False
    except AssertionError:
        print(msg + 'is not type ' + secret_type)
        return False
    return True

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

def validate_spec(kubeline_yaml):
    if not (type(kubeline_yaml) is dict and 'stages' in kubeline_yaml):
        print('ERROR - kubeline yaml file improperly formated')
        return False
    get_missing = lambda fields, stage: [f for f in fields if f not in stage]
    build_stages = []
    for stage in kubeline_yaml['stages']:
        msg = 'ERROR in stage {} - '.format(stage.get('name'))
        missing = get_missing(['name', 'type'], stage)
        if missing:
            print(msg + 'missing field(s) ', missing)
            return False
        valid_types = ['docker-build', 'docker-push']
        if stage['type'] not in valid_types:
            print(msg + 'invalid type')
            return False
        if stage['type'] == 'docker-build':
            build_stages.append(stage['name'])
            if 'build_dir' not in stage:
                stage['build_dir'] = '.'
            if 'dockerfile' not in stage:
                stage['dockerfile'] = 'Dockerfile'
        if stage['type'] == 'docker-push':
            missing = get_missing(['from_stage', 'repo', 'tags'], stage)
            if missing:
                print(msg + 'missing field(s) ', missing)
                return False
            if stage['from_stage'] not in build_stages:
                print(msg + 'from_stage', stage['from_stage'], 'not found')
                return False
            if ':' in stage['repo']:
                print(msg + 'repo field may not contain tags')
                return False
    return kubeline_yaml

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

