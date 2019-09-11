package jobs

var TplStr = `{{- $workDir := "/kubeline-work" -}}
{{- $logDir := "/kubeline-logs" -}}
{{- $logFile := printf "%s/$KUBELINE_STAGE_NAME" $logDir -}}
{{- $varsFile := printf "%s/vars.sh" $logDir -}}

{{- $stageStart := printf "KUBELINE_STAGE_STARTING" -}}
{{- $stageSuccess := printf "KUBELINE_STAGE_FINISHED" -}}
{{- $stageFailure := "KUBELINE_STAGE_FAILURE" -}}

{{- $dockerSecret := .DockerSecret -}}
{{- $gitBranch := .GitBranch -}}
{{- $gitCommit := .GitCommit -}}
{{- $gitCommitShort := substr 0 7 .GitCommit -}}
{{- $iteration := .KubelineIteration -}}

{{- $dockerImagePrefix := printf "kubeline-%s-%s" .Name $gitCommitShort -}}

{{- $failFunc := printf "function fail() {\n  echo '%s' >> %s 2>&1\n}" $stageFailure $logFile -}}
{{- $untilStr := printf "trap fail EXIT\nuntil [ -f %s ]; do sleep 1; done" $logFile -}}
{{- $failMsg := "exiting due to previous stage failure..." }}
{{- $grepStr := printf "if grep %s %s; then echo '%s'; exit 0; fi" $stageFailure $logFile $failMsg -}}
{{- $initScript := printf "%s\n%s\n%s\n" $failFunc $untilStr $grepStr -}}
{{- $exitString := printf "echo '%s' >> %s;trap : 0; exit 0" $stageSuccess $logFile -}}

---
apiVersion: batch/v1
kind: Job
metadata:
  generateName: "kl-{{ .Name }}-{{ .KubelineIteration }}-"
  namespace: {{ .Namespace }}
  labels:
    app: kubeline
    type: job
    pipeline: {{ .Name }}
    git_commit: {{ .GitCommit }}
    git_commit_short: {{ $gitCommitShort }}
spec:
  backoffLimit: 0
  completions: 1
  template:
    metadata:
      labels:
        app: kubeline
        type: job
        pipeline: {{ .Name }}
        git_commit: {{ .GitCommit }}
        git_commit_short: {{ $gitCommitShort }}
    spec:
      activeDeadlineSeconds: 4000
      restartPolicy: Never
      containers:

      {{- $stageName := "0-clone" }}
      - name: job-runner
        image: {{ .JobRunnerImage }}
        imagePullPolicy: Always
        args:
        - "{{ .Name }}"
        - --stages={{ range $i, $v := .Stages }}{{ add1 $i }}-{{ .Name }},{{ end }}{{ $stageName }}
        - --log-dir={{ $logDir }}
        - --start={{ $stageStart }}
        - --success={{ $stageSuccess }}
        - --failure={{ $stageFailure }}
        - --influxdb-host={{ .InfluxdbHost }}
        - --influxdb-db={{ .InfluxdbDB }}
        - --time-limit=3600
        volumeMounts:
        - name: logs
          mountPath: {{ $logDir }}

      - name: {{ $stageName }}
        image: alpine/git
        workingDir: {{ $workDir }}
        command: [sh]
        args:
        - -ceux
        - |-
          {{- $initScript | nindent 10 }}
          export GIT_SSH_COMMAND="ssh -o StrictHostKeyChecking=no"
          (
            git clone -q {{ .GitURL }} .
            git checkout -q {{ .GitCommit }}
          ) >> {{ $logFile }} 2>&1
          {{ $exitString }}
        env:
        - name: KUBELINE_STAGE_NAME
          value: {{ $stageName }}
        volumeMounts:
        - name: git-key
          subPath: {{ .GitKeySecretKey }}
          mountPath: /root/.ssh/id_rsa
        - name: work
          mountPath: {{ $workDir }}
        - name: logs
          mountPath: {{ $logDir }}

      {{- range $i, $v := .Stages }}
        {{- $stageNum := add1 $i }}
        {{- $stageName := printf "%d-%s" $stageNum .Name | replace "_" "-" }}
      - name: {{ $stageName }}
        {{- if eq .Type "docker-build" "docker-push" }}
        image: "alpine:3.9"
        {{- else }}
        image: {{ .Image }}
        {{- end }}
        workingDir: {{ $workDir }}
        command:
        - sh
        args:
        - -ceux
        - |-
          {{- $initScript | nindent 10 }}
          (
          {{- if eq .Type "docker-build" }}
            {{ $dockerImage := printf "%s-%s" $dockerImagePrefix .Name }}
            docker build -t {{ $dockerImage }} -f {{ .Dockerfile }} {{ .BuildDir }}
          {{- else if eq .Type "docker-push" }}
            {{- $dockerImage := printf "%s-%s" $dockerImagePrefix .FromStage }}
            {{- $repo := .Repo }}
            {{- range .Tags }}
            {{- $dest := printf "%s:%s" $repo . }}
            docker tag {{ $dockerImage}} "{{ $dest }}"
            docker push "{{ $dest }}"
            docker rmi "{{ $dest }}"
            {{- end }}
            docker rmi {{ $dockerImage }}
          {{- else }}
            {{- range .Commands }}
            {{ . | nindent 12 }}
            {{- end }}
          {{- end }}
          ) >> {{ $logFile }} 2>&1

          {{ $exitString }}

        env:
        - name: KUBELINE_ITERATION
          value: {{ $iteration | quote }}
        - name: KUBELINE_GIT_BRANCH
          value: {{ $gitBranch | quote }}
        - name: KUBELINE_GIT_COMMIT
          value: {{ $gitCommit | quote }}
        - name: KUBELINE_GIT_COMMIT_SHORT
          value: {{ $gitCommitShort | quote }}
        - name: KUBELINE_STAGE_NAME
          value: {{ $stageName | quote }}
        {{- if eq .Type "docker-push" }}
        - name: KUBELINE_DOCKER_IMAGE
          value: {{ printf "%s-%s" $dockerImagePrefix .Name | quote }}
        {{- end }}
        volumeMounts:
        - name: work
          mountPath: {{ $workDir }}
        - name: logs
          mountPath: {{ $logDir }}
        {{- if eq .Type "docker-build" "docker-push" }}
        - name: docker-socket
          mountPath: /var/run/docker.sock
        - name: docker-binary
          mountPath: /usr/bin/docker
        {{- if $dockerSecret }}
        - name: docker-creds
          subPath: .dockerconfigjson
          mountPath: /root/.docker/config.json
        {{- end }}
        {{- end }}
      {{- end }}

      volumes:
      - name: git-key
        secret:
          secretName: {{ .GitKeySecretName }}
          defaultMode: 0700
      - name: work
        emptyDir: {}
      - name: logs
        emptyDir:
          medium: Memory
      - name: docker-socket
        hostPath:
          path: /var/run/docker.sock
      - name: docker-binary
        hostPath:
          path: /usr/bin/docker
      {{- if .DockerSecret }}
      - name: docker-creds
        secret:
          secretName: {{ .DockerSecret }}
      {{- end }}
`
