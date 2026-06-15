package main

import (
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"os"
)

func getXmlRoot() (xml.Token, error) {
	path := "resources/c.xml"

	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read file: %w", err)
	}

	upper := bytes.ToUpper(raw)
	if bytes.Contains(upper, []byte("<!DOCTYPE")) || bytes.Contains(upper, []byte("<!ENTITY")) {
		return nil, errors.New("invalid XML: forbidden construct")
	}

	decoder := xml.NewDecoder(bytes.NewReader(raw))
	decoder.Strict = false
	decoder.AutoClose = xml.HTMLAutoClose
	decoder.Entity = xml.HTMLEntity

	token, err := decoder.Token()
	if err != nil {
		return nil, fmt.Errorf("failed to parse XML: %w", err)
	}

	if se, ok := token.(xml.StartElement); ok {
		return se, nil
	}

	return nil, errors.New("no root element found")
}