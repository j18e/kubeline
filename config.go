package main

import (
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"

	repopkg "github.com/j18e/kubeline/pkg/repos"
	log "github.com/sirupsen/logrus"
	"golang.org/x/crypto/ssh"
	"gopkg.in/yaml.v3"
)

const defaultReposDir = "tmp/repos"

type Config struct {
	GitKeySecretName string `yaml:"git_key_secret_name"`
	GitKeySecretKey  string `yaml:"git_key_secret_key"`
	InfluxdbHost     string `yaml:"influxdb_host"`
	InfluxdbDB       string `yaml:"influxdb_db"`
	ReposDir         string `yaml:"repos_dir"`

	Repos []repopkg.RepoConfig `yaml:"repos"`

	GitKeyBytes    []byte `yaml:"-"`
	Namespace      string `yaml:"-"`
	JobRunnerImage string `yaml:"-"`
}

func getConfig() (Config, []repopkg.Repo, error) {
	var config Config
	var repos []repopkg.Repo

	privKeyFile := flag.String("ssh.key", "", "path to private key file")
	configFile := flag.String("config.file", "", "path to yaml formatted config file")
	namespace := flag.String("k8s.namespace", "", "kubernetes namespace to run in")
	jobRunnerImage := flag.String("jobrunner.image", "", "docker repo:tag for the job runner")
	flag.Parse()

	if *privKeyFile == "" {
		return config, repos, errors.New("required parameter -ssh.key")
	} else if *configFile == "" {
		return config, repos, errors.New("required parameter -config.file")
	} else if *namespace == "" {
		return config, repos, errors.New("required parameter -k8s.namespace")
	} else if *jobRunnerImage == "" {
		return config, repos, errors.New("required parameter -jobrunner.image")
	}

	// load private key
	privKey, err := loadPrivateKey(*privKeyFile)
	if err != nil {
		return config, repos, err
	}

	// load config file
	if config, err = loadConfigFile(*configFile); err != nil {
		return config, repos, fmt.Errorf("loading config file: %v", err)
	}
	if config.ReposDir == "" {
		log.Infof("repos_dir not set in config. Using %s.", defaultReposDir)
		config.ReposDir = defaultReposDir
	}
	config.GitKeyBytes = privKey
	config.Namespace = *namespace
	config.JobRunnerImage = *jobRunnerImage

	log.Infof("initializing %d repos from config...", len(config.Repos))
	repoNames := make(map[string]bool)

	for _, repoCfg := range config.Repos {
		// make sure all repo names are unique
		if repoNames[repoCfg.Name] {
			return config, repos, fmt.Errorf("repo named %s appears multiple times in config", repoCfg.Name)
		}

		repoCfg.ParentDir = config.ReposDir

		// init and clone the repo
		repo, err := repopkg.NewRepo(repoCfg, config.GitKeyBytes)
		if err != nil {
			log.Errorf("init repo %s: %v", repoCfg.Name, err)
			continue
		}

		// add to the results
		repos = append(repos, repo)
		repoNames[repoCfg.Name] = true
	}
	log.Infof("%d/%d repos successfully initialized", len(repos), len(config.Repos))

	return config, repos, nil
}

func loadConfigFile(filename string) (Config, error) {
	var config Config
	bs, err := ioutil.ReadFile(filename)
	if err != nil {
		return config, err
	}
	if err = yaml.Unmarshal(bs, &config); err != nil {
		return config, err
	}
	return config, nil
}

func loadPrivateKey(filename string) ([]byte, error) {
	privKey, err := ioutil.ReadFile(filename)
	if err != nil {
		return privKey, err
	}
	pubKey, err := pubKeyStr(privKey)
	if err != nil {
		return privKey, err
	}
	log.Infof("Kubeline is using the following public key: %v", pubKey)
	return privKey, nil
}

func pubKeyStr(privKey []byte) (string, error) {
	block, _ := pem.Decode(privKey)
	priv, err := x509.ParsePKCS1PrivateKey(block.Bytes)
	if err != nil {
		return "", fmt.Errorf("parsing private key: %v", err)
	}
	pub, err := ssh.NewPublicKey(&priv.PublicKey)
	if err != nil {
		return "", fmt.Errorf("creating public key: %v", err)
	}

	pubKey := fmt.Sprintf("%s %s", pub.Type(),
		base64.StdEncoding.EncodeToString(pub.Marshal()))
	return pubKey, nil
}
