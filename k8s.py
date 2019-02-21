from jinja2 import Template, Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import UndefinedError
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from random import randint
from os import environ, path
import yaml

def Build(name, config, commit, kubeline_yaml):
    kubeline_yaml = validate_spec(kubeline_yaml)
    if not kubeline_yaml:
        return False
    template_file = 'templates/job.jinja.yml'
    env = Environment(loader=FileSystemLoader('.'), undefined=StrictUndefined)
    template = env.get_template(template_file)

    build_spec = {
        'name': name,
        'config': config,
        'commit': commit,
        'stages': kubeline_yaml['stages'],
    }
    body = template.render(build_spec)
    body = yaml.load(body)
    resp = trigger_build(body)
    return resp

def trigger_build(body):
    load_config()
    batch = client.BatchV1Api()
    resp = batch.create_namespaced_job(get_namespace(), body)
    return resp

def get_recent_job(pipeline):
    load_config()
    batch = client.BatchV1Api()
    namespace = get_namespace()
    labels = 'app=kubeline,pipeline={}'.format(pipeline)
    limit=20
    resp = batch.list_namespaced_job(namespace, label_selector=labels,
                                     limit=limit)
    if len(resp.items) == 0:
        return False
    results = [item for item in resp.items]
    while resp.metadata._continue:
        resp = batch.list_namespaced_job(namespace, label_selector=labels,
            limit=limit, _continue=resp.metadata._continue)
        for item in resp.items:
            results.append(item)
    return max(results, key=lambda r: r.status.start_time)

def check_secret(config):
    if not 'docker_secret' in config:
        return True
    load_config()
    namespace = get_namespace()
    core = client.CoreV1Api()
    msg = 'ERROR getting secret {} in namespace {} - '.format(config['docker_secret'], namespace)
    try:
        resp = core.read_namespaced_secret(config['docker_secret'], namespace)
        secret_type = 'kubernetes.io/dockerconfigjson'
        assert resp.type == secret_type
    except ApiException:
        print(msg + 'could not locate secret')
        return False
    except AssertionError:
        print(msg + 'is not type ' + secret_type)
        return False
    return True

def validate_spec(kubeline_yaml):
    get_missing = lambda fields, stage: [f for f in fields if f not in stage]
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
            if 'build_dir' not in stage:
                stage['build_dir'] = '.'
            if 'dockerfile' not in stage:
                stage['dockerfile'] = 'Dockerfile'
        if stage['type'] == 'docker-push':
            missing = get_missing(['from_stage', 'repo', 'tags'], stage)
            if missing:
                print(msg + 'missing field(s) ', missing)
                return False
            if stage['from_stage'] not in kubeline_yaml['stages']:
                print(msg + 'from_stage', stage['from_stage'], 'not found')
                return False
            if ':' in stage['repo']:
                print(msg + 'repo field may not contain tags')
                return False
    return kubeline_yaml

def get_namespace():
    namespace = 'default'
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

