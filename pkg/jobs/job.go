package jobs

import "github.com/j18e/kubeline/pkg/models"

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
