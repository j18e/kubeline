package models

//
// import (
// 	"io/ioutil"
//
// 	"gopkg.in/yaml.v3"
// )
//
// func getPipeline(c PipeConfig) (Pipeline, error) {
// 	var pipe Pipeline
//
// 	bs, err := ioutil.ReadFile("kubeline.yml")
// 	if err != nil {
// 		return pipe, err
// 	}
//
// 	err = yaml.Unmarshal(bs, &pipe)
// 	if err != nil {
// 		return pipe, err
// 	}
//
// 	err = pipe.Validate()
// 	if err != nil {
// 		return pipe, err
// 	}
// 	pipe.Commit = "o2j3f89qjo8h392"
// 	pipe.ShortCommit = pipe.Commit[:6]
//
// 	return pipe, nil
// }
