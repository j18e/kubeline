if [ "$(KUBELINE_STAGE_NUMBER)" -ne "1" ]; then
until [ -f "/stage-status/$((KUBELINE_STAGE_NUMBER-1))_COMPLETE" ]; do
    sleep 1
done
fi

echo "starting stage $(KUBELINE_STAGE_NUMBER): $(KUBELINE_STAGE_NAME)"
set -x
{% if stage['type'] == 'docker-build' %}
docker build -t $(KUBELINE_DOCKER_IMAGE) .
{% elif stage['type'] == 'docker-push' %}
for tag in $(KUBELINE_DOCKER_PUSH_TAGS); do
docker tag $(KUBELINE_DOCKER_IMAGE) ${tag}
docker push ${tag}
done
{% endif %}
set +x
echo "completed stage $(KUBELINE_STAGE_NUMBER): $(KUBELINE_STAGE_NAME)"
touch /stage-status/$(KUBELINE_STAGE_NUMBER)_COMPLETE
