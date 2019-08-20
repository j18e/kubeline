package json

import (
	"fmt"

	"github.com/j18e/kubeline/pkg/models"
	scribble "github.com/nanobox-io/golang-scribble"
	"gopkg.in/src-d/go-git.v4/plumbing"
)

type Storage struct {
	db   *scribble.Driver
	path string
}

type Commit struct {
	Hash plumbing.Hash
}

func NewStorage(storPath string) (*Storage, error) {
	var err error

	s := new(Storage)
	s.db, err = scribble.New(storPath, nil)
	if err != nil {
		return nil, err
	}

	s.path = storPath

	return s, nil
}

func (s *Storage) LastCommit(pipe models.PipeConfig) (plumbing.Hash, error) {
	var commit Commit
	emptyHash := plumbing.NewHash("")

	noFileStr := fmt.Sprintf("stat %s/%s/%s.json: no such file or directory", s.path, pipe.Name, pipe.Branch)
	err := s.db.Read(pipe.Name, pipe.Branch, &commit)
	if err != nil {
		if err.Error() == noFileStr {
			return emptyHash, nil
		}
		return emptyHash, err
	}
	return commit.Hash, nil
}

func (s *Storage) WriteCommit(pipe models.PipeConfig, hash plumbing.Hash) error {
	commit := Commit{hash}
	err := s.db.Write(pipe.Name, pipe.Branch, commit)
	return err
}
