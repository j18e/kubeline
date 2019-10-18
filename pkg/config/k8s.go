package config

import (
	"errors"
	"fmt"
	"io/ioutil"
	"os"

	"github.com/ericchiang/k8s"
	"github.com/ghodss/yaml"
	log "github.com/sirupsen/logrus"
)

func (c *Config) loadK8sClient(namespace string) error {
	cli, err := k8s.NewInClusterClient()
	if err == nil {
		c.Client = cli
		return nil
	}

	path := os.Getenv("HOME") + "/.kube/config"
	log.Infof("looks like we're not running inside k8s. Loading kubeconfig from %s", path)
	data, err := ioutil.ReadFile(path)
	if err != nil {
		return fmt.Errorf("reading %s: %v", path, err)
	}
	var kc k8s.Config
	if err := yaml.Unmarshal(data, &kc); err != nil {
		return fmt.Errorf("unmarshaling %s: %v", path, err)
	}
	cli, err = k8s.NewClient(&kc)
	if err != nil {
		return err
	}
	c.Client = cli
	if namespace == "" {
		return errors.New("flag -namespace required when loading out of cluster")
	}
	c.Client.Namespace = namespace
	log.Infof("using k8s namespace %s", c.Client.Namespace)
	return nil
}
