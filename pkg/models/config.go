package models

import (
	"gopkg.in/src-d/go-git.v4/plumbing/transport"
	gitssh "gopkg.in/src-d/go-git.v4/plumbing/transport/ssh"
)

type PipeConfigList struct {
	Pipelines []PipeConfig `yaml:"pipelines"`
}

type PipeConfig struct {
	Name         string `yaml:"name"`
	URL          string `yaml:"git_url"`
	Branch       string `yaml:"git_branch"`
	DockerSecret string `yaml:"docker_secret"`

	Auth transport.AuthMethod `yaml:"-"`
}

func (pipe *PipeConfig) Init(privKey []byte) error {
	endpoint, err := transport.NewEndpoint(pipe.URL)
	if err != nil {
		return err
	}
	if endpoint.Protocol == "ssh" {
		auth, err := gitssh.NewPublicKeys(endpoint.User, privKey, "")
		if err != nil {
			return err
		}
		pipe.Auth = auth
	}
	if pipe.Branch == "" {
		pipe.Branch = "master"
	}
	return nil
}
