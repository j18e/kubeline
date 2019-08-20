package models

import (
	"errors"
	"fmt"
)

type Stage struct {
	Type string `yaml:"type"`
	Name string `yaml:"name"`

	// Docker build
	BuildDir   string `yaml:"build_dir"`
	Dockerfile string `yaml:"dockerfile"`

	// Docker Push
	FromStage string   `yaml:"from_stage"`
	Repo      string   `yaml:"repo"`
	Tags      []string `yaml:"tags"`

	// Custom
	Image    string   `yaml:"image"`
	Commands []string `yaml:"commands"`
}

func (s *Stage) Validate() error {
	if s.Name == "" {
		return fmt.Errorf("must specify stage name")
	}

	switch s.Type {
	case "docker-build":
		if s.BuildDir == "" {
			s.BuildDir = "."
		}
		if s.Dockerfile == "" {
			s.Dockerfile = "./Dockerfile"
		}
	case "docker-push":
		if s.FromStage == "" {
			return errors.New("must specify from_stage")
		} else if s.Repo == "" {
			return errors.New("must specify destination Docker repo")
		}
		if len(s.Tags) == 0 {
			s.Tags = []string{"latest"}
		}
	case "custom":
		if s.Image == "" {
			return errors.New("must specify stage image")
		} else if len(s.Commands) == 0 {
			return errors.New("must specify stage commands")
		}
	default:
		return fmt.Errorf("unknown stage type %s", s.Type)
	}
	return nil
}
