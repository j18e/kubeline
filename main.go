package main

import (
	"flag"
	"fmt"

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
		runTemplate(conf, n)
	}
}

func runTemplate(conf config.Config, name string) {
	// get the repo from the config
	rc, err := conf.GetRepo(name)
	if err != nil {
		log.Fatal(err)
	}
	log.Infof("rendering template of repo %s", rc.Name)

	// open/clone repo
	repo, err := repos.NewRepo(rc, conf.ReposDir, conf.PrivateKeyBytes)
	if err != nil {
		log.Fatal(err)
	}

	// pull latest changes
	if err := repo.Pull(); err != nil {
		log.Fatalf("pulling repo: %v", err)
	}

	// render the template
	rendered, err := jobs.RenderJob(repo, conf)
	if err != nil {
		log.Fatal(err)
	}
	fmt.Println(*rendered)
}

// func getConfig() (Config, []repopkg.Repo, error) {
// 	log.Infof("initializing %d repos from config...", len(config.Repos))
// 	repoNames := make(map[string]bool)
//
// 	for _, repoCfg := range config.Repos {
// 		// make sure all repo names are unique
// 		if repoNames[repoCfg.Name] {
// 			return config, repos, fmt.Errorf("repo named %s appears multiple times in config", repoCfg.Name)
// 		}
//
// 		repoCfg.ParentDir = config.ReposDir
//
// 		// init and clone the repo
// 		repo, err := repopkg.NewRepo(repoCfg, config.GitKeyBytes)
// 		if err != nil {
// 			log.Errorf("init repo %s: %v", repoCfg.Name, err)
// 			continue
// 		}
//
// 		// add to the results
// 		repos = append(repos, repo)
// 		repoNames[repoCfg.Name] = true
// 	}
// 	log.Infof("%d/%d repos successfully initialized", len(repos), len(config.Repos))
//
// 	return config, repos, nil
// }
