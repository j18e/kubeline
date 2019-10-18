package repos

import (
	"errors"

	"github.com/prometheus/common/log"
	"gopkg.in/src-d/go-git.v4/plumbing/transport"
)

const DefaultBranchName = "master"

type RepoConfig struct {
	Name         string `json:"name"`
	URL          string `json:"git_url"`
	Branch       string `json:"git_branch"`
	DockerSecret string `json:"docker_secret"`
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
