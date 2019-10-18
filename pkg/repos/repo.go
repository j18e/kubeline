package repos

import (
	"errors"
	"fmt"
	"io/ioutil"
	"os"

	"github.com/ghodss/yaml"
	"github.com/j18e/kubeline/pkg/models"
	"github.com/prometheus/common/log"
	git "gopkg.in/src-d/go-git.v4"
	gitconfig "gopkg.in/src-d/go-git.v4/config"
	"gopkg.in/src-d/go-git.v4/plumbing"
	"gopkg.in/src-d/go-git.v4/plumbing/transport"
	"gopkg.in/src-d/go-git.v4/plumbing/transport/ssh"
	"gopkg.in/src-d/go-git.v4/storage/memory"
)

const (
	KubelineYAMLFilePath = "/kubeline.yml"
	RemoteName           = "origin"
)

type Repo struct {
	Name         string
	Path         string
	URL          string
	BranchRef    *plumbing.Reference
	auth         transport.AuthMethod
	DockerSecret string
	repo         *git.Repository
	worktree     *git.Worktree
}

type RepoList []*Repo

func (rx RepoList) Get(name string) (*Repo, error) {
	for _, r := range rx {
		if r.Name == name {
			return r, nil
		}
	}
	return &Repo{}, fmt.Errorf("repo %s not found", name)
}

func NewRepo(config *RepoConfig, dir string, privKey *[]byte) (*Repo, error) {
	repo := &Repo{
		Name:         config.Name,
		Path:         dir + "/" + config.Name,
		URL:          config.URL,
		DockerSecret: config.DockerSecret,
	}

	if err := repo.getAuth(config.URL, privKey); err != nil {
		return repo, err
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
	repo.worktree = wt

	if err := repo.worktree.Checkout(&git.CheckoutOptions{Branch: repo.BranchRef.Name()}); err != nil {
		return fmt.Errorf("checking out %s: %v", repo.BranchRef.Name().Short(), err)
	}

	log.Infof("repo %s exists at %s, checked out %s", repo.Name, repo.Path, repo.BranchRef.Name().Short())
	return nil
}

func (repo *Repo) Pull() error {
	err := repo.worktree.Pull(&git.PullOptions{
		RemoteName:    RemoteName,
		ReferenceName: repo.BranchRef.Name(),
		SingleBranch:  true,
		Auth:          repo.auth,
	})
	if err == git.NoErrAlreadyUpToDate {
		return nil
	} else if err != nil {
		return err
	}
	log.Infof("pulled latest on %s/%s", repo.Name, repo.BranchRef.Name().Short())
	return nil
}

func (repo *Repo) clone() error {
	log.Infof("cleaning path %s for repo %s...", repo.Path, repo.Name)
	os.RemoveAll(repo.Path)

	r, err := git.PlainClone(repo.Path, false,
		&git.CloneOptions{
			URL:               repo.URL,
			Auth:              repo.auth,
			ReferenceName:     repo.BranchRef.Name(),
			RecurseSubmodules: git.DefaultSubmoduleRecursionDepth,
		})
	if err != nil {
		os.RemoveAll(repo.Path)
		return err
	}
	repo.repo = r
	wt, err := repo.repo.Worktree()
	if err != nil {
		return fmt.Errorf("getting worktree: %v", err)
	}
	repo.worktree = wt
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

func (repo *Repo) branchRef(config *RepoConfig) error {
	errNotFound := errors.New("branch not found on remote")

	rem := git.NewRemote(memory.NewStorage(), &gitconfig.RemoteConfig{
		Name: RemoteName,
		URLs: []string{config.URL},
	})

	refs, err := rem.List(&git.ListOptions{repo.auth})
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

func (repo *Repo) getAuth(url string, privKey *[]byte) error {
	endpoint, err := transport.NewEndpoint(url)
	if err != nil {
		return err
	}
	switch endpoint.Protocol {
	case "ssh":
		auth, err := ssh.NewPublicKeys(endpoint.User, *privKey, "")
		if err != nil {
			return err
		}
		repo.auth = auth
	case "https":
	default:
		return fmt.Errorf("unknown protocol %s in url %s", endpoint.Protocol, url)
	}
	return nil
}
