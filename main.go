package main

import (
	"context"
	"flag"
	"fmt"
	"net/http"

	batch "github.com/ericchiang/k8s/apis/batch/v1"
	"github.com/ghodss/yaml"
	"github.com/gin-gonic/gin"
	"github.com/j18e/kubeline/pkg/config"
	"github.com/j18e/kubeline/pkg/jobs"
	"github.com/j18e/kubeline/pkg/repos"
	log "github.com/sirupsen/logrus"
)

func main() {
	conf, err := config.LoadConfig()
	if err != nil {
		log.Fatalf("loading config: %v", err)
	}

	// handle command
	switch conf.Command {
	case config.TEMPLATE:
		n := flag.Arg(1)
		if n == "" {
			log.Fatal("no repo name provided")
		}
		bx, err := runTemplate(conf, n)
		if err != nil {
			log.Fatal(err)
		}
		fmt.Println(string(*bx))
	case config.TRIGGER:
		n := flag.Arg(1)
		if n == "" {
			log.Fatal("no repo name provided")
		}
		bx, err := runTemplate(conf, n)
		if err != nil {
			log.Fatal(err)
		}
		if err := runTrigger(conf, bx); err != nil {
			log.Fatal(err)
		}
		log.Infof("successfully triggered %s", n)
	case config.SERVE:
		runServe(conf)
	}
}

func runServe(conf config.Config) {
	var repoList repos.RepoList
	log.Infof("initializing %d repos...", len(conf.Repos))
	for _, rc := range conf.Repos {
		repo, err := repos.NewRepo(rc, conf.DataDir, conf.PrivateKeyBytes)
		if err != nil {
			log.Errorf("processing %s: %v", rc.Name, err)
			continue
		}
		repoList = append(repoList, repo)
	}
	log.Infof("%d/%d repos initialized", len(repoList), len(conf.Repos))

	router := gin.Default()
	router.GET("/api/run/:name", func(c *gin.Context) {
		name := c.Param("name")
		repo, err := repoList.Get(name)
		if err != nil {
			c.String(http.StatusBadRequest, err.Error())
			return
		}
		c.String(http.StatusOK, "triggering %s", name)

		// pull latest changes
		if err := repo.Pull(); err != nil {
			log.Errorf("error pulling %s: %v", name, err)
			return
		}
		// render the template
		jobBytes, err := jobs.RenderJob(repo, conf)
		if err != nil {
			log.Errorf("error rendering job for %s: %v", name, err)
			return
		}
		// create the job in k8s
		if err := runTrigger(conf, jobBytes); err != nil {
			log.Errorf("error triggering job for %s: %v", name, err)
			return
		}
		log.Info("successfully triggered", name)
		return
	})

	router.Run("localhost:8080")
}

func runTemplate(conf config.Config, name string) (*[]byte, error) {
	var bx *[]byte

	// get the repo from the config
	rc, err := conf.GetRepo(name)
	if err != nil {
		return bx, err
	}
	log.Infof("rendering template of repo %s", rc.Name)

	// open/clone repo
	repo, err := repos.NewRepo(rc, conf.DataDir, conf.PrivateKeyBytes)
	if err != nil {
		return bx, err
	}

	// pull latest changes
	if err := repo.Pull(); err != nil {
		return bx, fmt.Errorf("pulling repo: %v", err)
	}

	// render the template
	bx, err = jobs.RenderJob(repo, conf)
	if err != nil {
		return bx, fmt.Errorf("rendering job: %v", err)
	}

	return bx, nil
}

func runTrigger(conf config.Config, jobBytes *[]byte) error {
	// unmarshal yaml into a Kubernetes job object.
	var job batch.Job
	if err := yaml.Unmarshal(*jobBytes, &job); err != nil {
		return fmt.Errorf("unmarshalling yaml job manifest: %v", err)
	}
	// send the job to k8s
	if err := conf.Client.Create(context.TODO(), &job); err != nil {
		return fmt.Errorf("creating job in k8s: %v", err)
	}
	return nil
}
