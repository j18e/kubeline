package main

import (
	"fmt"
	"log"
	"os"
	"path"
	"runtime"

	"github.com/j18e/kubeline/pkg/checking"
	"github.com/j18e/kubeline/pkg/storage/json"
)

func main() {
	conf, err := getConfig()
	if err != nil {
		log.Fatal(err)
	}

	_, filename, _, _ := runtime.Caller(0)
	p := path.Dir(filename)
	storPath := p + "/tmp/json-storage/"

	stor, err := json.NewStorage(storPath)
	if err != nil {
		log.Fatal(err)
	}
	checker := checking.NewService(stor)

	for _, pipe := range conf.pipes {
		changed, err := checker.CheckPipe(pipe)
		if err != nil {
			fmt.Fprintf(os.Stderr, "ERROR check %s on %s: %v\n", pipe.Name, pipe.Branch, err)
		}
		if changed {
			kly, hash, err := checker.FetchKubelineYAML(pipe)
			if err != nil {
				fmt.Println(err)
			}
			fmt.Printf("TRIGGER %s on %s at %s\n", pipe.Name, pipe.Branch, hash.String())
			fmt.Println(kly)
		}
	}

	// tpl, err := template.New("").Parse(tplStr)
	// if err != nil {
	// 	log.Fatalln(err)
	// }
	// err = tpl.Execute(os.Stdout, pipe)
}
