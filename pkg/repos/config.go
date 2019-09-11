package repos

import (
	"errors"

	"github.com/prometheus/common/log"
	"gopkg.in/src-d/go-git.v4/plumbing/transport"
)

const DefaultBranchName = "master"

type RepoConfig struct {
	Name         string `yaml:"name"`
	URL          string `yaml:"git_url"`
	Branch       string `yaml:"git_branch"`
	DockerSecret string `yaml:"docker_secret"`
}

func (rc *RepoConfig) Validate() error {
	if rc.Name == "" {
		return errors.New("required field name")
	} else if _, err := transport.NewEndpoint(rc.URL); err != nil {
		return err
	}
	if rc.Branch == "" {
		log.Debugf("repo %s branch not set, setting to %s", rc.Name, DefaultBranchName)
		rc.Branch = DefaultBranchName
	}
	return nil
}
