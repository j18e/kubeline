from jinja2 import Template, Environment, FileSystemLoader, StrictUndefined
from jinja2.exceptions import UndefinedError
from kubernetes import client, config
from random import randint
from os import environ, path
import yaml

def Build(build_spec):
    if not validate_spec(build_spec):
        return False
    template_file = 'templates/job.jinja.yml'
    env = Environment(loader=FileSystemLoader('.'), undefined=StrictUndefined)
    template = env.get_template(template_file)
    body = template.render(build_spec)
    body = yaml.load(body)
    resp = trigger_build(body)
    return resp.metadata.creation_timestamp

def trigger_build(body):
    if path.isfile(environ['HOME'] + '/.kube/config'):
        config.load_kube_config()
        namespace = 'default'
    else:
        config.load_incluster_config()
        namespace = '/var/run/secrets/kubernetes.io/serviceaccount/namespace'
        with open(namespace_file, 'r') as stream:
            namespace = stream.read()
    batch = client.BatchV1Api()
    resp = batch.create_namespaced_job(namespace, body)
    return resp

def validate_spec(spec):
    for idx, stage in enumerate(spec['stages']):
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

