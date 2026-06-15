package main

import (
	"encoding/xml"
	"os"
)

func getXmlRoot() xml.Token {
	// Create an XML parser and parse the resources/c.xml file and return the root element
	file, _ := os.Open("resources/c.xml")
	decoder := xml.NewDecoder(file)
	for {
		t, _ := decoder.Token()
		if t == nil {
			break
		}
		switch se := t.(type) {
		case xml.StartElement:
			return se
		}
	}
	return nil
}