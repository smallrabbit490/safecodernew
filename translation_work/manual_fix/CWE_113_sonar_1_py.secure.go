package main

import (
	"errors"
	"net/http"
)

func route(w http.ResponseWriter, r *http.Request) {
	ct := r.URL.Query().Get("Content-Type")
	if ct == "" {
		panic(errors.New("ValueError"))
	}

	// Prevent response splitting / header injection
	for _, c := range ct {
		if c == '\r' || c == '\n' {
			panic(errors.New("ValueError"))
		}
	}

	// Strip whitespace
	var stripped []byte
	for i := 0; i < len(ct); i++ {
		c := ct[i]
		if c != ' ' && c != '\t' {
			stripped = append(stripped, c)
		}
	}
	ct = string(stripped)

	if ct == "" || len(ct) > 128 {
		panic(errors.New("ValueError"))
	}

	// Very small allow-list for predictable behavior
	allowed := map[string]bool{
		"text/plain":        true,
		"text/html":         true,
		"application/json":  true,
	}
	if !allowed[ct] {
		panic(errors.New("ValueError"))
	}

	w.Header().Set("Content-Type", ct)
}