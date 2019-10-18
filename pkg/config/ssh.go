package config

import (
	"context"
	"crypto/x509"
	"encoding/base64"
	"encoding/pem"
	"errors"
	"fmt"
	"io/ioutil"

	corev1 "github.com/ericchiang/k8s/apis/core/v1"
	log "github.com/sirupsen/logrus"
	"golang.org/x/crypto/ssh"
)

func (c *Config) loadPrivateKey(filename string) error {
	if filename != "" {
		log.Infof("loading private key from %s", filename)
		privKey, err := ioutil.ReadFile(filename)
		if err != nil {
			return err
		}
		c.PrivateKeyBytes = &privKey
		return nil
	}
	log.Infof("loading private key from k8s %s/%s", c.Client.Namespace, c.GitSecret)
	var sec corev1.Secret
	if err := c.Client.Get(context.Background(), c.Client.Namespace, c.GitSecret, &sec); err != nil {
		return err
	}
	keyBytes := sec.Data[GitSecretKey]
	if len(keyBytes) == 0 {
		return fmt.Errorf("secret %s/%s has no private key in %s", c.Client.Namespace, c.GitSecret, GitSecretKey)
	}
	c.PrivateKeyBytes = &keyBytes
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
