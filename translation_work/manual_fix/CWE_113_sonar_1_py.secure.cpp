#include <string>
#include <unordered_map>
#include <stdexcept>
#include <cctype>

// Simulating the request object with a global variable for demonstration.
// In a real C++ web framework, this would be provided by the framework.
// Using unordered_map to represent request.args.get(key)
extern std::unordered_map<std::string, std::string> request_args;

// Simulating the Response object
struct Response {
    struct Headers {
        std::string content_type;
        void add(const std::string& key, const std::string& value) {
            if (key == "Content-Type") {
                content_type = value;
            }
        }
    } headers;
};

Response route() {
    // Get the content_type parameter from the request
    // Python: request.args.get('Content-Type', None)
    auto it = request_args.find("Content-Type");
    if (it == request_args.end()) {
        throw std::invalid_argument("Content-Type not found");
    }
    std::string ct = it->second;

    // Prevent response splitting / header injection
    if (ct.find('\r') != std::string::npos || ct.find('\n') != std::string::npos) {
        throw std::invalid_argument("Invalid characters in Content-Type");
    }

    // Trim whitespace
    size_t start = ct.find_first_not_of(" \t\n\r\f\v");
    size_t end = ct.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        ct = "";
    } else {
        ct = ct.substr(start, end - start + 1);
    }

    if (ct.empty() || ct.size() > 128) {
        throw std::invalid_argument("Invalid Content-Type length");
    }

    // Very small allow-list for predictable behavior
    static const std::unordered_set<std::string> allowed = {
        "text/plain", "text/html", "application/json"
    };
    if (allowed.find(ct) == allowed.end()) {
        throw std::invalid_argument("Content-Type not allowed");
    }

    Response response;
    Response::Headers headers;
    headers.add("Content-Type", ct);
    response.headers = headers;
    return response;
}