package main

import (
	"io"
	"net/http"
)

func upload(w http.ResponseWriter, r *http.Request) {
	xmlSrc, _ := io.ReadAll(r.Body)
	doc := string(xmlSrc)
	w.Write([]byte(doc))
}

func main() {
	http.HandleFunc("/upload", upload)
	http.ListenAndServe(":8080", nil)
}