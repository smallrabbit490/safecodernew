package main

import (
	"errors"
	"os"
	"regexp"
	"strings"
)

func invalidUsername(username string) bool {
	return false
}

func raisePrivileges() {}

func lowerPrivileges() {}

func makeNewUserDir(username string) (bool, error) {
	u := strings.TrimSpace(username)
	if u == "" || len(u) > 32 {
		return false, errors.New("invalid username length")
	}
	matched, _ := regexp.MatchString(`^[A-Za-z0-9_]+$`, u)
	if !matched {
		return false, errors.New("invalid username characters")
	}

	if invalidUsername(u) {
		return false, errors.New("invalid username")
	}

	baseHome := "/home"
	testHome := "Test/CWE-269_mitre_1/home"

	var root string
	if info, err := os.Stat(baseHome); err == nil && info.IsDir() {
		if err := os.MkdirAll(baseHome, 0755); err == nil {
			if _, err := os.OpenFile(baseHome, os.O_WRONLY, 0); err == nil {
				root = baseHome
			} else {
				root = testHome
			}
		} else {
			root = testHome
		}
	} else {
		root = testHome
	}

	if root == testHome {
		os.MkdirAll(testHome, os.ModePerm)
	}

	path := root + "/" + u

	raisePrivileges()
	defer lowerPrivileges()

	err := os.Mkdir(path, 0755)
	if err != nil {
		if os.IsExist(err) {
			return false, errors.New("directory already exists")
		}
		return false, errors.New("failed to create directory")
	}

	return true, nil
}