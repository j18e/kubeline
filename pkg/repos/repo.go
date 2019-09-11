package repos

import (
	"errors"
	"fmt"
	"io/ioutil"
	"os"

	"github.com/j18e/kubeline/pkg/models"
	"github.com/prometheus/common/log"
	git "gopkg.in/src-d/go-git.v4"
	gitconfig "gopkg.in/src-d/go-git.v4/config"
	"gopkg.in/src-d/go-git.v4/plumbing"
	"gopkg.in/src-d/go-git.v4/plumbing/transport"
	"gopkg.in/src-d/go-git.v4/plumbing/transport/ssh"
	"gopkg.in/src-d/go-git.v4/storage/memory"
	"gopkg.in/yaml.v2"
)

const (
	DefaultBranchName    = "master"
	KubelineYAMLFilePath = "/kubeline.yml"
	RemoteName           = "origin"
)

type RepoConfig struct {
	Name         string `yaml:"name"`
	URL          string `yaml:"git_url"`
	Branch       string `yaml:"git_branch"`
	DockerSecret string `yaml:"docker_secret"`

	ParentDir string `yaml:"-"`
}

type Repo struct {
	Name         string
	Path         string
	URL          string
	BranchRef    *plumbing.Reference
	Auth         transport.AuthMethod
	Repo         *git.Repository
	DockerSecret string
}

func NewRepo(config RepoConfig, privKey []byte) (Repo, error) {
	repo := Repo{
		Name:         config.Name,
		Path:         config.ParentDir + "/" + config.Name,
		URL:          config.URL,
		DockerSecret: config.DockerSecret,
	}

	if err := repo.getAuth(config.URL, privKey); err != nil {
		return repo, err
	}

	if config.Branch == "" {
		log.Debugf("repo %s branch not set, setting to %s", config.Name, DefaultBranchName)
		config.Branch = DefaultBranchName
	}

	if err := repo.branchRef(config); err != nil {
		return repo, fmt.Errorf("getting branch ref: %v", err)
	}

	if err := repo.open(); err != nil {
		if err := repo.clone(); err != nil {
			return repo, fmt.Errorf("cloning repo: %v", err)
		}
	}

	return repo, nil
}

// open checks whether the repo's configured path already exists. If it
// does exist but is not a git repo, pathExists will forcefully remove
// everything under the path.
func (repo *Repo) open() error {
	// try opening the repo as if it already exists
	r, err := git.PlainOpen(repo.Path)
	if err != nil {
		return err
	}

	rem, err := r.Remote(RemoteName)
	if err != nil {
		return err
	}
	urls := rem.Config().URLs
	if len(urls) < 1 {
		return fmt.Errorf("no url's found for remote %s", RemoteName)
	}
	if urls[0] != repo.URL {
		return fmt.Errorf("expected remote url %s but found %s", repo.URL, urls[0])
	}

	wt, err := r.Worktree()
	if err != nil {
		return fmt.Errorf("getting worktree: %v", err)
	}

	if err := wt.Checkout(&git.CheckoutOptions{Branch: repo.BranchRef.Name()}); err != nil {
		return fmt.Errorf("checking out %s: %v", repo.BranchRef.Name().Short(), err)
	}

	log.Infof("repo %s exists at %s, checked out %s", repo.Name, repo.Path, repo.BranchRef.Name().Short())
	return nil
}

func (repo *Repo) clone() error {
	log.Infof("cleaning path %s for repo %s...", repo.Path, repo.Name)
	os.RemoveAll(repo.Path)

	gitRepo, err := git.PlainClone(repo.Path, false,
		&git.CloneOptions{
			URL:               repo.URL,
			Auth:              repo.Auth,
			ReferenceName:     repo.BranchRef.Name(),
			RecurseSubmodules: git.DefaultSubmoduleRecursionDepth,
		})
	if err != nil {
		os.RemoveAll(repo.Path)
		return err
	}
	repo.Repo = gitRepo
	return nil
}

func (repo *Repo) GetKubelineYAML() (models.KubelineYAML, error) {
	var ky models.KubelineYAML

	bs, err := ioutil.ReadFile(repo.Path + "/" + KubelineYAMLFilePath)
	if err != nil {
		return ky, err
	}

	if err = yaml.Unmarshal(bs, &ky); err != nil {
		return ky, err
	}

	return ky, nil
}

func (repo *Repo) branchRef(config RepoConfig) error {
	errNotFound := errors.New("branch not found on remote")

	rem := git.NewRemote(memory.NewStorage(), &gitconfig.RemoteConfig{
		Name: RemoteName,
		URLs: []string{config.URL},
	})

	refs, err := rem.List(&git.ListOptions{repo.Auth})
	if err != nil {
		return err
	}

	for _, ref := range refs {
		if ref.Name().IsBranch() && ref.Name().Short() == config.Branch {
			repo.BranchRef = ref
			return nil
		}
	}
	return errNotFound
}

func (repo *Repo) getAuth(url string, privKey []byte) error {
	endpoint, err := transport.NewEndpoint(url)
	if err != nil {
		return err
	}
	switch endpoint.Protocol {
	case "ssh":
		auth, err := ssh.NewPublicKeys(endpoint.User, privKey, "")
		if err != nil {
			return err
		}
		repo.Auth = auth
	case "https":
	default:
		return fmt.Errorf("unknown protocol %s in url %s", endpoint.Protocol, url)
	}
	return nil
}
