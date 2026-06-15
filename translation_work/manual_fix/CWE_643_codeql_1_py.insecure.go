package main

import (
	"encoding/xml"
	"fmt"
	"net/http"
	"strings"
)

func xpathQuery(w http.ResponseWriter, r *http.Request) {
	value := r.URL.Query().Get("xpath")
	xmlStr := r.URL.Query().Get("xml")

	type Tag struct {
		XMLName xml.Name `xml:"tag"`
		Id      string   `xml:"id,attr"`
		Content string   `xml:",chardata"`
	}

	var tags []Tag
	decoder := xml.NewDecoder(strings.NewReader(xmlStr))
	for {
		var t Tag
		err := decoder.Decode(&t)
		if err != nil {
			break
		}
		tags = append(tags, t)
	}

	var results []string
	_ = fmt.Sprintf("/tag[@id='%s']", value) // Constructed to match Python logic, though Go's stdlib doesn't support dynamic XPath evaluation
	for _, t := range tags {
		if t.Id == value {
			results = append(results, t.Content)
		}
	}

	w.Write([]byte(fmt.Sprintf("%v", results)))
}

func main() {
	http.HandleFunc("/xpath_query", xpathQuery)
	http.ListenAndServe(":8080", nil)
}