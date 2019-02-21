from jinja2 import Template, Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import UndefinedError
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from random import randint
from os import environ, path
import yaml

def Build(name, config, commit, kubeline_yaml):
    if not validate_spec(kubeline_yaml):
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

def get_job_commit(pipeline):
    load_config()
    batch = client.BatchV1Api()
    namespace = get_namespace()
    label_selector = 'app=kubeline,pipeline={}'.format(pipeline)
    resp = batch.list_namespaced_job(namespace, label_selector=label_selector)
    if len(resp.items) == 0:
        return False
    recent_build = resp.items[0]
    for build in resp.items:
        if build.status.start_time > recent_build.status.start_time:
            recent_build = build
    return recent_build.metadata.labels['commit']

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
    for idx, stage in enumerate(kubeline_yaml['stages']):
        required_fields = ['name', 'type']
        valid_types = ['docker-build', 'docker-push']
        msg = 'ERROR in stage {} - '.format(idx+1)
        for field in required_fields:
            if not field in stage:
                print(msg + 'required field {}'.format(field))
                return False
        if stage['type'] not in valid_types:
            print(msg + 'invalid type')
            return False
        if stage['type'] == 'docker-push':
            if (':' in stage.get('repo')) or ('repo' not in stage):
                print(msg + 'repo field absent or misconfigured')
                return False
            if not stage.get('tags'):
                print(msg + 'docker push stage must contain list of tags')
                return False
    return True

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

