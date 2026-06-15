#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <stdexcept>
#include <algorithm>
#include <cctype>
#include <functional>

// Helper function to convert a string to uppercase
std::string to_upper(const std::string& str) {
    std::string result = str;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c){ return std::toupper(c); });
    return result;
}

// Helper function to check if a string contains a substring
bool contains(const std::string& str, const std::string& substr) {
    return str.find(substr) != std::string::npos;
}

// Simple XML parser implementation
class SimpleXMLParser {
private:
    std::string content;
    size_t pos;

    void skip_whitespace() {
        while (pos < content.size() && std::isspace(static_cast<unsigned char>(content[pos]))) {
            pos++;
        }
    }

    std::string read_name() {
        std::string name;
        while (pos < content.size() && 
               (std::isalnum(static_cast<unsigned char>(content[pos])) || content[pos] == '_' || content[pos] == '-' || content[pos] == ':')) {
            name += content[pos++];
        }
        return name;
    }

public:
    SimpleXMLParser(const std::string& xml) : content(xml), pos(0) {}

    std::string parse() {
        skip_whitespace();
        if (pos >= content.size() || content[pos] != '<') {
            throw std::runtime_error("Invalid XML");
        }
        pos++; // skip '<'
        
        // Check for comments or processing instructions
        if (pos < content.size() && content[pos] == '!') {
            throw std::runtime_error("Comments and processing instructions not supported");
        }
        
        // Check for XML declaration
        if (pos < content.size() && content[pos] == '?') {
            while (pos < content.size() && !(content[pos] == '?' && content[pos+1] == '>')) {
                pos++;
            }
            if (pos >= content.size()) {
                throw std::runtime_error("Unclosed XML declaration");
            }
            pos += 2; // skip '?>'
            skip_whitespace();
            if (pos >= content.size() || content[pos] != '<') {
                throw std::runtime_error("Expected root element");
            }
            pos++; // skip '<'
        }
        
        std::string root_name = read_name();
        if (root_name.empty()) {
            throw std::runtime_error("Invalid root element name");
        }

        // Basic validation: ensure the root tag is closed properly
        // We look for the closing tag </root_name>
        std::string closing_tag = "</" + root_name + ">";
        if (content.find(closing_tag) == std::string::npos) {
            throw std::runtime_error("Malformed XML: Root element not closed");
        }
        
        return root_name;
    }
};

std::string getXmlRoot() {
    std::string path = "resources/c.xml";
    std::string raw;
    
    try {
        std::ifstream file(path, std::ios::binary);
        if (!file) {
            throw std::runtime_error("Failed to open file");
        }
        
        std::ostringstream oss;
        oss << file.rdbuf();
        raw = oss.str();
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to read file");
    }
    
    std::string upper = to_upper(raw);
    if (contains(upper, "<!DOCTYPE") || contains(upper, "<!ENTITY")) {
        throw std::invalid_argument("DOCTYPE or ENTITY found");
    }
    
    try {
        SimpleXMLParser parser(raw);
        return parser.parse();
    } catch (const std::exception& e) {
        throw std::invalid_argument("Failed to parse XML");
    }
}