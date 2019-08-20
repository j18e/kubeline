package main

import (
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"

	"github.com/j18e/kubeline/pkg/models"
	"golang.org/x/crypto/ssh"
	"gopkg.in/yaml.v3"
)

type config struct {
	privKey []byte
	pipes   []models.PipeConfig
}

func getConfig() (config, error) {
	var conf config

	privKeyFile := flag.String("ssh.key", "", "path to private key file")
	configFile := flag.String("config.file", "", "path to yaml formatted config file")
	flag.Parse()

	if *privKeyFile == "" {
		return conf, errors.New("must specify -ssh.key")
	}
	if *configFile == "" {
		return conf, errors.New("must specify -config.file")
	}

	// load private key, print public key
	privKey, err := ioutil.ReadFile(*privKeyFile)
	if err != nil {
		log.Fatal(err)
	}
	conf.privKey = privKey
	pubKey, err := pubKeyStr(privKey)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println("Kubeline is using the following public key:", pubKey)

	// load config file
	bs, err := ioutil.ReadFile("dev/config.yml")
	if err != nil {
		log.Fatal(err)
	}

	var pipeConfigList models.PipeConfigList
	err = yaml.Unmarshal(bs, &pipeConfigList)
	if err != nil {
		log.Fatal(err)
	}

	fmt.Printf("initializing %d pipelines from config...\n", len(pipeConfigList.Pipelines))
	for _, pipe := range pipeConfigList.Pipelines {
		err := pipe.Init(conf.privKey)
		if err != nil {
			fmt.Fprintf(os.Stderr, "ERROR initializing pipeline %s: %v", pipe.Name, err)
			continue
		}
		conf.pipes = append(conf.pipes, pipe)
	}
	fmt.Printf("%d/%d pipelines successfully initialized\n", len(conf.pipes), len(pipeConfigList.Pipelines))

	return conf, nil
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
