package main

import (
	"fmt"
	"log"
	"os"
	"text/template"

	"github.com/Masterminds/sprig"
	"github.com/j18e/kubeline/pkg/jobs"
	"github.com/j18e/kubeline/pkg/repos"
)

func fail(s string) {
	fmt.Fprintln(os.Stderr, "FAILURE - "+s)
	os.Exit(1)
}

func main() {
	config, repos, err := getConfig()
	if err != nil {
		fail(err.Error())
	}

	triggerJob(config, repos[0])
}

func triggerJob(config Config, repo repos.Repo) {
	tpl, err := template.New("job").Funcs(sprig.TxtFuncMap()).Parse(jobs.TplStr)
	if err != nil {
		log.Fatalf("templating job: %v", err)
	}

	ky, err := repo.GetKubelineYAML()
	if err != nil {
		log.Fatalf("getting kubeline.yml: %v", err)
	}

	if err := ky.Validate(); err != nil {
		log.Fatalf("validating kubeline.yml: %v", err)
	}

	parms := jobs.JobParameters{
		Name:              repo.Name,
		Stages:            ky.Stages,
		KubelineIteration: 7,
		GitURL:            repo.URL,
		GitBranch:         repo.BranchRef.Name().Short(),
		GitCommit:         repo.BranchRef.Hash().String(),
		GitKeySecretName:  config.GitKeySecretName,
		GitKeySecretKey:   config.GitKeySecretKey,
		JobRunnerImage:    config.JobRunnerImage,
		InfluxdbHost:      config.InfluxdbHost,
		InfluxdbDB:        config.InfluxdbDB,
		Namespace:         config.Namespace,
		DockerSecret:      repo.DockerSecret,
	}

	err = tpl.Execute(os.Stdout, parms)
	if err != nil {
		log.Fatal(err)
	}
}
