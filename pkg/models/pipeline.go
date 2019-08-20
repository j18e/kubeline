package models

import (
	"errors"
	"fmt"
)

type KubelineYAML struct {
	Stages      []Stage `yaml:"stages"`
	Commit      string  `yaml:"-"`
	ShortCommit string  `yaml:"-"`
}

func (p *KubelineYAML) Validate() error {
	if len(p.Stages) == 0 {
		return errors.New("pipeline must contain at least one stage")
	}

	for i, s := range p.Stages {
		err := s.Validate()
		if err != nil {
			return fmt.Errorf("stage %d: %v", i+1, s)
		}
	}

	return nil
}
