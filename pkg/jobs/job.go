package jobs

import (
	"bytes"
	"fmt"
	"text/template"

	"github.com/Masterminds/sprig"
	"github.com/j18e/kubeline/pkg/config"
	"github.com/j18e/kubeline/pkg/models"
	"github.com/j18e/kubeline/pkg/repos"
)

type JobParameters struct {
	Stages []*models.Stage

	Name              string
	KubelineIteration int
	GitURL            string
	GitBranch         string
	GitCommit         string
	GitKeySecretName  string
	GitKeySecretKey   string
	DockerSecret      string
	JobRunnerImage    string
	InfluxdbHost      string
	InfluxdbDB        string
	Namespace         string
}

func RenderJob(repo repos.Repo, conf config.Config) (*string, error) {
	str := ""

	tpl, err := template.New("job").Funcs(sprig.TxtFuncMap()).Parse(tplStr)
	if err != nil {
		return &str, fmt.Errorf("creating template: %v", err)
	}

	ky, err := repo.GetKubelineYAML()
	if err != nil {
		return &str, fmt.Errorf("getting kubeline.yml: %v", err)
	}

	if err := ky.Validate(); err != nil {
		return &str, fmt.Errorf("validating kubeline.yml: %v", err)
	}

	parms := JobParameters{
		Name:              repo.Name,
		Stages:            ky.Stages,
		KubelineIteration: 1,
		GitURL:            repo.URL,
		GitBranch:         repo.BranchRef.Name().Short(),
		GitCommit:         repo.BranchRef.Hash().String(),
		DockerSecret:      repo.DockerSecret,
		GitKeySecretName:  conf.GitKeySecretName,
		GitKeySecretKey:   conf.GitKeySecretKey,
		JobRunnerImage:    conf.JobRunnerImage,
		InfluxdbHost:      conf.InfluxdbHost,
		InfluxdbDB:        conf.InfluxdbDB,
		Namespace:         conf.Namespace,
	}

	// execute the template
	buf := new(bytes.Buffer)
	if err = tpl.Execute(buf, parms); err != nil {
		return &str, err
	}
	str = buf.String()

	return &str, nil
}
