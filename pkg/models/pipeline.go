package models

import (
	"errors"
	"fmt"
)

type KubelineYAML struct {
	Stages []*Stage `json:"stages"`
}

func (ky *KubelineYAML) Validate() error {
	if len(ky.Stages) < 1 {
		return errors.New("pipeline must contain at least one stage")
	}

	for _, s := range ky.Stages {
		err := s.Validate()
		if err != nil {
			return fmt.Errorf("stage %s: %v", s.Name, err)
		}
	}

	return nil
}
