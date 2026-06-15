package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"io"
)

// Global variable to simulate the request object
var requestData []byte

func upload() []byte {
	// Check if request data is available
	if requestData == nil {
		panic(errors.New("type error"))
	}

	// Ensure data is bytes
	b := make([]byte, len(requestData))
	copy(b, requestData)

	// Convert to uppercase for DTD/ENTITY check
	upper := bytes.ToUpper(b)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		panic(errors.New("value error"))
	}

	// Parse XML
	decoder := xml.NewDecoder(bytes.NewReader(b))
	decoder.Strict = true
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	var root interface{}
	if err := decoder.Decode(&root); err != nil && err != io.EOF {
		panic(errors.New("value error"))
	}

	// Convert back to XML string
	output, err := xml.Marshal(root)
	if err != nil {
		panic(errors.New("value error"))
	}

	// Add XML declaration if not present
	if !bytes.HasPrefix(output, []byte("<?xml")) {
		output = append([]byte(`<?xml version="1.0" encoding="UTF-8"?>`), output...)
	}

	return output
}

func main() {
	// Example usage would set requestData before calling upload()
}