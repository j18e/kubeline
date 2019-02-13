from kubernetes import client, config
import yaml

def Build(args, name, pipeline, iteration=None, git_commit=None):
    if args['dev']:
        config.load_kube_config()
    else:
        config.load_incluster_config()
    batch = client.BatchV1Api()
    namespace = 'default'
    with open('templates/job.yml', 'r') as stream:
        body = yaml.load(stream.read())

    body['metadata']['generateName'] = name + '-'
    body['metadata']['labels']['app'] = 'kubeline'
    body['metadata']['labels']['pipeline'] = name

    if iteration:
        body['metadata']['labels']['iteration'] = str(iteration)
        body['spec']['template']['spec']['initContainers'][0]['env'].append(
            {'name': 'GIT_URL', 'value': pipeline['git_url']})
    if git_commit:
        body['metadata']['labels']['git_commit'] = git_commit
        body['spec']['template']['spec']['initContainers'][0]['env'].append(
            {'name': 'GIT_COMMIT', 'value': git_commit})

    resp = batch.create_namespaced_job(namespace, body)
    return resp.metadata.creation_timestamp

