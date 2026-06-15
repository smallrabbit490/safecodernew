package main

import (
	"net/http"
)

func route(w http.ResponseWriter, r *http.Request) {
	contentType := r.URL.Query().Get("Content-Type")
	w.Header().Set("Content-Type", contentType)
}