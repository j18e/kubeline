package config

import (
	"errors"
	"flag"
	"fmt"
	"io/ioutil"

	"github.com/ericchiang/k8s"
	"github.com/ghodss/yaml"
	"github.com/j18e/kubeline/pkg/repos"
	log "github.com/sirupsen/logrus"
)

const (
	defaultDataDir = "tmp/kubeline"
	GitSecretKey   = "id_rsa"
)

type Command int

const (
	TEMPLATE Command = iota
	TRIGGER
	SERVE
)

type Config struct {
	GitSecret      string `json:"git_secret_name"`
	InfluxdbHost   string `json:"influxdb_host"`
	InfluxdbDB     string `json:"influxdb_db"`
	JobRunnerImage string `json:"job_runner_image"`

	Repos []*repos.RepoConfig `json:"repos"`

	DataDir         string      `json:"-"`
	PrivateKeyBytes *[]byte     `json:"-"`
	Command         Command     `json:"-"`
	Client          *k8s.Client `json:"-"`
	namespace       string      `json:"-"`
}

func (c *Config) GetRepo(name string) (*repos.RepoConfig, error) {
	for _, r := range c.Repos {
		if r.Name == name {
			return r, nil
		}
	}
	return &repos.RepoConfig{}, fmt.Errorf("repo %s not found in config", name)
}

func LoadConfig() (Config, error) {
	var conf Config

	// define command line flags
	configFile := flag.String("config.file", "", "path to the config file")
	privKeyFile := flag.String("ssh.key", "", "specify a local private key for checking out Git repos")
	namespace := flag.String("namespace", "", "specify Kubernetes namespace to use")
	dataDir := flag.String("data.dir", defaultDataDir, "specify data directory")
	flag.Parse()

	// load config file
	if *configFile == "" {
		return conf, errors.New("required flag -config.file")
	}
	if err := loadConfigFile(*configFile, &conf); err != nil {
		return conf, err
	}

	// parse command
	errValidCmds := errors.New("valid commands [template trigger serve]")
	switch flag.Arg(0) {
	case "template":
		conf.Command = TEMPLATE
	case "trigger":
		conf.Command = TRIGGER
	case "serve":
		conf.Command = SERVE
	default:
		return conf, errValidCmds
	}

	// check config fields which are universally required
	switch {
	case conf.GitSecret == "":
		return conf, errors.New("required field git_key_secret_name")
	case conf.InfluxdbHost == "":
		return conf, errors.New("required field influxdb_host")
	case conf.InfluxdbDB == "":
		return conf, errors.New("required field influxdb_db")
	case conf.JobRunnerImage == "":
		return conf, errors.New("required field job_runner_image")
	case len(conf.Repos) == 0:
		return conf, errors.New("at least 1 repo must be configured")
	}

	if err := conf.loadK8sClient(*namespace); err != nil {
		return conf, fmt.Errorf("loading k8s client: %v", err)
	}

	conf.DataDir = *dataDir
	if conf.DataDir == defaultDataDir {
		log.Infof("using default data dir %s. Customize with -data.dir", defaultDataDir)
	}

	// load private key bytes into conf
	if err := conf.loadPrivateKey(*privKeyFile); err != nil {
		return conf, err
	}

	if err := conf.validateRepos(); err != nil {
		return conf, err
	}

	return conf, nil
}

func (c *Config) validateRepos() error {
	names := make(map[string]bool)

	for _, r := range c.Repos {
		if names[r.Name] {
			return fmt.Errorf("config.repos: %s appears multiple times", r.Name)
		} else if err := r.Validate(); err != nil {
			return fmt.Errorf("config.repos: validate %s: %v", r.Name, err)
		}
		names[r.Name] = true
	}
	return nil
}

func loadConfigFile(filename string, conf *Config) error {
	bs, err := ioutil.ReadFile(filename)
	if err != nil {
		return err
	}
	if err = yaml.Unmarshal(bs, conf); err != nil {
		return err
	}
	return nil
}
