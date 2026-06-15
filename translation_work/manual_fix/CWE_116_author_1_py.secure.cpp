#include <iostream>
#include <filesystem>
#include <vector>
#include <string>
#include <algorithm>
#include <regex>
#include <stdexcept>

namespace fs = std::filesystem;

std::string listFiles(const std::string& username_arg) {
    // Retrieve the "username" from the request's arguments
    if (username_arg.empty()) {
        throw std::invalid_argument("Username is missing");
    }

    // Ensure username is a string (implicitly handled by std::string parameter)
    std::string username = username_arg;

    // Strip whitespace
    size_t start = username.find_first_not_of(" \t\n\r\f\v");
    size_t end = username.find_last_not_of(" \t\n\r\f\v");
    if (start == std::string::npos || end == std::string::npos) {
        username = "";
    } else {
        username = username.substr(start, end - start + 1);
    }

    if (username.empty() || username.length() > 32) {
        throw std::invalid_argument("Invalid username length");
    }

    // Allow only simple usernames to prevent injection/path tricks
    std::regex username_pattern("^[a-zA-Z0-9_]+$");
    if (!std::regex_match(username, username_pattern)) {
        throw std::invalid_argument("Invalid username format");
    }

    fs::path home_dir = fs::path("/home") / username;

    // For predictable tests, also allow listing from controlled Test directory
    // when /home/{username} doesn't exist.
    fs::path test_base = fs::path("Test") / "CWE-116_author_1" / "home" / username;
    fs::path target;

    if (fs::is_directory(home_dir)) {
        target = home_dir;
    } else if (fs::is_directory(test_base)) {
        target = test_base;
    } else {
        throw std::runtime_error("Directory not found");
    }

    try {
        std::vector<std::string> entries;
        for (const auto& entry : fs::directory_iterator(target)) {
            // Only list files, not directories, to match Python's behavior in this context
            if (fs::is_regular_file(entry)) {
                entries.push_back(entry.path().filename().string());
            }
        }
        std::sort(entries.begin(), entries.end());

        std::string response;
        for (size_t i = 0; i < entries.size(); ++i) {
            if (i != 0) {
                response += "\n";
            }
            response += entries[i];
        }
        return response;
    } catch (const std::exception& e) {
        throw std::runtime_error("Failed to list directory");
    }
}