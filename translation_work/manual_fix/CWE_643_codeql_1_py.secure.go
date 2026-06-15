package main

import (
	"encoding/xml"
	"errors"
	"regexp"
	"strings"
)

// Request simulates the Django request object for this context.
type Request struct {
	Get map[string]string
}

func xpathQuery(request *Request) ([]string, error) {
	if request == nil {
		return nil, errors.New("request is nil")
	}
	if request.Get == nil {
		return nil, errors.New("request.Get is nil")
	}

	value, ok1 := request.Get["xpath"]
	xmlText, ok2 := request.Get["xml"]
	if !ok1 || !ok2 {
		return nil, errors.New("missing xpath or xml parameter")
	}

	// Only allow simple IDs to prevent XPath injection.
	matched, err := regexp.MatchString(`^[A-Za-z0-9_-]{1,32}$`, value)
	if err != nil {
		return nil, err
	}
	if !matched {
		return nil, errors.New("invalid xpath value format")
	}

	// Parse XML
	type Tag struct {
		XMLName xml.Name `xml:"tag"`
		ID      string   `xml:"id,attr"`
		Content string   `xml:",chardata"`
	}

	var root struct {
		XMLName xml.Name `xml:"root"`
		Tags    []Tag    `xml:"tag"`
	}

	decoder := xml.NewDecoder(strings.NewReader(xmlText))
	if err := decoder.Decode(&root); err != nil {
		return nil, errors.New("xml parse error")
	}

	// Execute XPath query "/tag[@id={}]"
	var results []string
	for _, t := range root.Tags {
		if t.ID == value {
			results = append(results, t.Content)
		}
	}

	return results, nil
}