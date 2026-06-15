#include <string>
#include <map>
#include <stdexcept>
#include <regex>
#include <tinyxml2.h>

std::string xpath_query(const std::map<std::string, std::string>& request) {
    // Check if 'xpath' and 'xml' keys exist in the request
    if (request.find("xpath") == request.end() || request.find("xml") == request.end()) {
        throw std::invalid_argument("Missing 'xpath' or 'xml' in request");
    }

    std::string value = request.at("xpath");
    std::string xml_text = request.at("xml");

    // Only allow simple IDs to prevent XPath injection.
    std::regex id_pattern(R"([A-Za-z0-9_-]{1,32})");
    if (!std::regex_match(value, id_pattern)) {
        throw std::invalid_argument("Invalid XPath value");
    }

    // Parse XML using tinyxml2
    tinyxml2::XMLDocument doc;
    tinyxml2::XMLError result = doc.Parse(xml_text.c_str());
    if (result != tinyxml2::XML_SUCCESS) {
        throw std::invalid_argument("Failed to parse XML");
    }

    // Construct the XPath query manually
    // Note: tinyxml2 does not support full XPath or variable binding like lxml.
    // We emulate the specific query "/tag[@id='value']" safely.
    std::string xpath_query_str = "/tag[@id='" + value + "']";

    // Find the first element matching the tag name "tag"
    tinyxml2::XMLElement* root = doc.FirstChildElement("tag");
    std::string output;

    // Iterate through all 'tag' elements to find the one with the matching ID
    for (tinyxml2::XMLElement* node = root; node != nullptr; node = node->NextSiblingElement("tag")) {
        const char* id_attr = node->Attribute("id");
        if (id_attr != nullptr && std::string(id_attr) == value) {
            // Found the matching node, get its text content
            const char* content = node->GetText();
            if (content != nullptr) {
                output = content;
            }
            break;
        }
    }

    return output;
}