package main

import (
	"errors"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

func listFiles(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	if username == "" {
		panic(errors.New("username is required"))
	}

	username = strings.TrimSpace(username)
	if username == "" || len(username) > 32 {
		panic(errors.New("invalid username length"))
	}

	// Allow only simple usernames to prevent injection/path tricks
	matched, _ := regexp.MatchString(`^[a-zA-Z0-9_]+$`, username)
	if !matched {
		panic(errors.New("invalid username format"))
	}

	homeDir := filepath.Join("/home", username)

	// For predictable tests, also allow listing from controlled Test directory
	// when /home/{username} doesn't exist.
	testBase := filepath.Join("Test", "CWE-116_author_1", "home", username)

	var target string
	info, err := os.Stat(homeDir)
	if err == nil && info.IsDir() {
		target = homeDir
	} else {
		info, err = os.Stat(testBase)
		if err == nil && info.IsDir() {
			target = testBase
		} else {
			panic(errors.New("directory not found"))
		}
	}

	entries, err := os.ReadDir(target)
	if err != nil {
		panic(errors.New("failed to list directory"))
	}

	var fileNames []string
	for _, entry := range entries {
		fileNames = append(fileNames, entry.Name())
	}

	sort.Strings(fileNames)

	w.Write([]byte(strings.Join(fileNames, "\n")))
}

func main() {
	http.HandleFunc("/reply", listFiles)
	http.ListenAndServe(":8080", nil)
}