from jinja2 import Template
from kubernetes import client, config
from random import randint
from os import environ, path
import yaml

gen_var = lambda x, y : {'name': 'KUBELINE_' + x, 'value': y}

def Build(name, git_url, pipeline_config, commit_sha, iteration=0):
    env_vars = get_env(git_url, commit_sha)
    labels = get_labels(name, commit_sha, iteration)
    containers = []
    for idx, stage in enumerate(pipeline_config['stages']):
        if not validate_stage(stage, str(idx+1)):
            return False
        containers.append(generate_container(stage, str(idx+1), get_env(git_url, commit_sha)))

    with open('templates/job.yml', 'r') as stream:
        body = yaml.load(stream.read())
    with open('templates/init-container-git-clone.yml', 'r') as stream:
        container_clone = yaml.load(stream.read())

    container_clone['env'] = get_env(git_url, commit_sha)

    body['metadata']['generateName'] = name + '-'
    body['metadata']['labels'] = labels
    body['spec']['template']['metadata']['labels'] = labels
    body['spec']['template']['spec']['containers'] = containers
    body['spec']['template']['spec']['initContainers'].append(container_clone)

    resp = trigger_build(body)
    return resp.metadata.creation_timestamp

def trigger_build(body):
    if path.isfile(environ['HOME'] + '/.kube/config'):
        config.load_kube_config()
    else:
        config.load_incluster_config()
    batch = client.BatchV1Api()
    namespace = 'default'
    resp = batch.create_namespaced_job(namespace, body)
    return resp

def validate_stage(stage, stage_number):
    required_fields = ['name', 'type']
    valid_types = ['docker-build', 'docker-push']
    msg = 'ERROR in stage {} - '.format(stage_number)
    for field in required_fields:
        if not field in stage:
            print(msg + 'required field {}'.format(field))
            return False
    if stage['type'] not in valid_types:
        print(msg + 'invalid type')
        return False
    if stage['type'] == 'docker-push':
        try:
            assert len(stage['repo'].split(':')) < 3
        except:
            print(msg + 'repo field absent or misconfigured')
            return False
    return True

def generate_container(stage, stage_number, env):
    with open('templates/stage.jinja.sh', 'r') as stream:
        shell_template = Template(stream.read())
    container = {
        'name': stage['name'],
        'image': 'alpine:3.9',
        'workingDir': '/work',
        'command': ['sh'],
        'args': ['-ceu', shell_template.render(stage=stage)],
        'volumeMounts': get_volume_mounts(stage),
    }
    if stage['type'] == 'docker-push':
        if not stage.get('additional_tags'):
            repo_tags = stage['repo']
        else:
            repo = stage['repo'].split(':')[0]
            repo_tags = stage['repo']
            for tag in stage['additional_tags']:
                repo_tags = repo_tags + ' {}:{}'.format(repo, tag)
        env.append(gen_var('DOCKER_PUSH_TAGS', repo_tags.strip()))
    env.append(gen_var('STAGE_NAME', stage['name']))
    env.append(gen_var('STAGE_NUMBER', stage_number))
    container['env'] = env
    return container

def get_env(git_url, commit_sha):
    env = [
        gen_var('GIT_URL', git_url),
        gen_var('COMMIT_SHA', commit_sha),
        gen_var('COMMIT_SHA_SHORT', commit_sha[:6]),
        gen_var('DOCKER_IMAGE', 'kubeline-docker-image')
    ]
    return env

def get_labels(name, commit_sha, iteration):
    labels = {
        'app': 'kubeline',
        'pipeline': name,
        'commit-sha': commit_sha[:6],
        'iteration': str(iteration)
    }
    return labels

def get_volume_mounts(stage):
    volume_mounts = [
        {'name': 'work', 'mountPath': '/work'},
        {'name': 'status', 'mountPath': '/stage-status'},
    ]
    if stage['type'] in ['docker-build', 'docker-push']:
        volume_mounts.append({'name': 'docker-socket',
                              'mountPath': '/var/run/docker.sock'})
        volume_mounts.append({'name': 'docker-binary',
                              'mountPath': '/usr/bin/docker'},
        )
        volume_mounts.append({'name': 'docker-creds',
                              'mountPath': '/root/.docker/config.json',
                              'subPath': '.dockerconfigjson'})
    return volume_mounts

