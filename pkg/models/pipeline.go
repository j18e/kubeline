package models

import (
	"errors"
	"fmt"
)

type KubelineYAML struct {
	Stages []*Stage `yaml:"stages"`
}

func (ky *KubelineYAML) Validate() error {
	if len(ky.Stages) < 1 {
		return errors.New("pipeline must contain at least one stage")
	}

	for i, s := range ky.Stages {
		err := s.Validate()
		if err != nil {
			return fmt.Errorf("stage %d: %v", i+1, s)
		}
	}

	return nil
}
