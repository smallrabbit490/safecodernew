package main

import (
	"fmt"
	"io/ioutil"
	"net/http"
	"os/exec"
)

func listFiles(w http.ResponseWriter, r *http.Request) {
	username := r.URL.Query().Get("username")
	cmd := exec.Command("sh", "-c", fmt.Sprintf("cd /home/%s && ls -l > /tmp/files.txt", username))
	cmd.Run()
	files, _ := ioutil.ReadFile("/tmp/files.txt")
	w.Write(files)
}

func main() {
	http.HandleFunc("/reply", listFiles)
	http.ListenAndServe(":8080", nil)
}