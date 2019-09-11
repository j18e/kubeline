package config

import (
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"

	"github.com/j18e/kubeline/pkg/repos"
	log "github.com/sirupsen/logrus"
	"golang.org/x/crypto/ssh"
	"gopkg.in/yaml.v3"
)

const defaultReposDir = "tmp/repos"

type Command int

const (
	TEMPLATE Command = iota
)

type Config struct {
	GitKeySecretName string `yaml:"git_key_secret_name"`
	GitKeySecretKey  string `yaml:"git_key_secret_key"`
	InfluxdbHost     string `yaml:"influxdb_host"`
	InfluxdbDB       string `yaml:"influxdb_db"`
	JobRunnerImage   string `yaml:"job_runner_image"`
	ReposDir         string `yaml:"repos_dir"`

	Repos []*repos.RepoConfig `yaml:"repos"`

	PrivateKeyBytes *[]byte `yaml:"-"`
	Namespace       string  `yaml:"-"`
	Command         Command `yaml:"-"`
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
	flag.Parse()

	// parse command
	errValidCmds := errors.New("valid commands [template]")
	switch flag.Arg(0) {
	case "template":
		conf.Command = TEMPLATE
	default:
		return conf, errValidCmds
	}

	// load config file
	if *configFile == "" {
		return conf, errors.New("required flag -config.file")
	}
	if err := loadConfigFile(*configFile, &conf); err != nil {
		return conf, err
	}

	// check config fields which are universally required
	switch {
	case conf.GitKeySecretName == "":
		return conf, errors.New("required field git_key_secret_name")
	case conf.GitKeySecretKey == "":
		return conf, errors.New("required field git_key_secret_key")
	case conf.InfluxdbHost == "":
		return conf, errors.New("required field influxdb_host")
	case conf.InfluxdbDB == "":
		return conf, errors.New("required field influxdb_db")
	case conf.JobRunnerImage == "":
		return conf, errors.New("required field job_runner_image")
	case *namespace == "":
		return conf, errors.New("TODO derive k8s namespace. Use -namespace flag") // TODO
	case len(conf.Repos) == 0:
		return conf, errors.New("at least 1 repo must be configured")
	}

	if conf.ReposDir == "" {
		log.Infof("repos_dir not set. Using %s.", defaultReposDir)
		conf.ReposDir = defaultReposDir
	}

	// load private key from file, if specified
	if *privKeyFile != "" {
		if err := conf.loadPrivateKey(*privKeyFile); err != nil {
			return conf, err
		}
	} else {
		return conf, errors.New("TODO implement loading of private keys from k8s. Use -ssh.key flag") // TODO
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

func (c *Config) loadPrivateKey(filename string) error {
	log.Infof("loading private key from %s", filename)
	privKey, err := ioutil.ReadFile(filename)
	if err != nil {
		return err
	}
	c.PrivateKeyBytes = &privKey
	return nil
}

func (c *Config) PrintPublicKey() error {
	if len(*c.PrivateKeyBytes) == 0 {
		return errors.New("private key not loaded")
	}
	block, _ := pem.Decode(*c.PrivateKeyBytes)
	priv, err := x509.ParsePKCS1PrivateKey(block.Bytes)
	if err != nil {
		return fmt.Errorf("parsing private key: %v", err)
	}
	pub, err := ssh.NewPublicKey(&priv.PublicKey)
	if err != nil {
		return fmt.Errorf("creating public key: %v", err)
	}

	pubKey := fmt.Sprintf("%s %s", pub.Type(),
		base64.StdEncoding.EncodeToString(pub.Marshal()))

	fmt.Println("using the following public key:", pubKey)

	return nil
}
