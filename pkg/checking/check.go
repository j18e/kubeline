package checking

import (
	"errors"
	"io/ioutil"
	"os"

	"github.com/j18e/kubeline/pkg/models"
	"gopkg.in/src-d/go-git.v4"
	"gopkg.in/src-d/go-git.v4/config"
	"gopkg.in/src-d/go-git.v4/plumbing"
	"gopkg.in/src-d/go-git.v4/storage/memory"
	"gopkg.in/yaml.v2"
)

type Repository interface {
	LastCommit(models.PipeConfig) (plumbing.Hash, error)
	WriteCommit(models.PipeConfig, plumbing.Hash) error
}

type Service interface {
	CheckPipe(models.PipeConfig) (bool, error)
	FetchKubelineYAML(models.PipeConfig) (models.KubelineYAML, plumbing.Hash, error)
}

type service struct {
	r Repository
}

func NewService(r Repository) Service {
	return &service{r}
}

// CheckPipe compares the most recent hash of a given git remote/branch against
// the commit (if any) in storage, and returns true if the two differ.
func (s *service) CheckPipe(pipe models.PipeConfig) (bool, error) {
	var emptyHash = plumbing.NewHash("")

	remoteHash, err := hashFromRemote(pipe)
	if err != nil {
		return false, err
	}
	localHash, err := s.r.LastCommit(pipe)
	if err != nil {
		return false, err
	}

	if localHash == remoteHash {
		return false, nil
	}

	err = s.r.WriteCommit(pipe, remoteHash)
	if err != nil {
		return false, err
	}

	if localHash == emptyHash {
		return false, nil
	}

	return true, nil
}

func hashFromRemote(pipe models.PipeConfig) (plumbing.Hash, error) {
	errNotFound := errors.New("branch not found on remote")
	emptyHash := plumbing.Hash{}

	rem := git.NewRemote(memory.NewStorage(), &config.RemoteConfig{
		Name: "origin",
		URLs: []string{pipe.URL},
	})

	refs, err := rem.List(&git.ListOptions{pipe.Auth})
	if err != nil {
		return emptyHash, err
	}

	for _, ref := range refs {
		if ref.Name().IsBranch() && ref.Name().Short() == pipe.Branch {
			return ref.Hash(), nil
		}
	}
	return emptyHash, errNotFound
}

func (s *service) FetchKubelineYAML(pipe models.PipeConfig) (models.KubelineYAML, plumbing.Hash, error) {
	var kubelineYAML models.KubelineYAML

	hash, err := s.r.LastCommit(pipe)
	if err != nil {
		return kubelineYAML, hash, err
	}
	if hash.String() == "" {
		hash, err = hashFromRemote(pipe)
		if err != nil {
			return kubelineYAML, hash, err
		}
	}

	cloneDir := "tmp/repos/" + hash.String()

	_, err = git.PlainClone(cloneDir, false,
		&git.CloneOptions{
			URL:               pipe.URL,
			Auth:              pipe.Auth,
			ReferenceName:     plumbing.ReferenceName("refs/heads/" + pipe.Branch),
			RecurseSubmodules: git.DefaultSubmoduleRecursionDepth,
		})
	if err != nil {
		return kubelineYAML, hash, err
	}
	defer os.RemoveAll(cloneDir)

	bs, err := ioutil.ReadFile(cloneDir + "/kubeline.yml")
	if err != nil {
		return kubelineYAML, hash, err
	}

	err = yaml.Unmarshal(bs, &kubelineYAML)
	if err != nil {
		return kubelineYAML, hash, err
	}

	return kubelineYAML, hash, nil
}
