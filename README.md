# Kubeline
A Kubernetes native CI tool

![Dashboard][1]

## Components
- Custom built job triggerer
- Pipelines are executed as Kubernetes jobs
- InfluxDB hosts job status metrics as well as log output from job stages
- Grafana visualises pipeline/job status/logs

## High level overview
- Kubeline runs in a Kubernetes cluster, watching the Git repos specified in its
  config file
- Each Git repo must contain a pipeline spec at `/kubeline.yml`. Example:
```
stages:
- name: build
  type: docker-build
- name: push
  type: docker-push
  from_stage: build
  repo: j18e/kubeline
  tags:
  - latest
  - $KUBELINE_COMMIT_SHA_SHORT
```
- When a pipeline is triggered (either manually or by a change in Git), Kubeline
  reads the `kubeline.yml` file from the Git repo and triggers a Kubernetes job
  that will run each stage as specified, in sequence.
- The outcome of the job can be reviewed as it's occurring in Grafana

## Docker credentials
In order for pulls of private Docker repositories and all pushes to occur,
authentication is required in the Docker stages. For this purpose Kubernetes
[image pull secrets][2] are leveraged. Here's how it works:
- an image pull secret with credentials to perform the desired pull/push
  operations must be created in the namespace in which builds are being run
- in the server side config file, a pipeline configuration can contain the name
  of the secret (see below)
- upon running the build, the secret will be mounted to the pod, and attached to
  any docker-build and docker-push stages
- The secret is mounted to docker stages at `~/.docker/config.json`, from the
  file `.dockerconfig.json` in the secret. Therefore the default pattern of
  creating `imagePullSecret` must be followed, otherwise Docker auth won't work

The aforementioned pipeline config containing the secret name:
```
pipelines:
  test-1:
    url: https://github.com/j18e/ci-test-1
    branch: master
    docker_secret: kubeline-docker-test-1
```
Along with this config, the `imagePullSecret` has been created using Kubectl (or
a manifest file):
```
kubectl create secret docker-registry kubeline-docker-test-1 \
    --docker-username=j18e \
    --docker-password=$(cat password-file) \
    --docker-server=https://index.docker.io/v1 # not necessary if authenticating to Docker hub
```

[1]: dev/example-dashboard.png
[2]: https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/
