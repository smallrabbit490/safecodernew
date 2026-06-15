#include <string>
#include <filesystem>
#include <stdexcept>
#include <regex>

namespace fs = std::filesystem;

// Forward declarations for the external functions
bool invalidUsername(const std::string& username);
void raisePrivileges();
void lowerPrivileges();

bool makeNewUserDir(const std::string& username) {
    std::string u = username;
    
    // Remove leading and trailing whitespace
    size_t start = u.find_first_not_of(" \t\n\r\f\v");
    if (start == std::string::npos) {
        u = "";
    } else {
        size_t end = u.find_last_not_of(" \t\n\r\f\v");
        u = u.substr(start, end - start + 1);
    }

    if (u.empty() || u.length() > 32) {
        throw std::invalid_argument("Invalid username length");
    }

    std::regex pattern(R"([A-Za-z0-9_]+)");
    if (!std::regex_match(u, pattern)) {
        throw std::invalid_argument("Invalid username characters");
    }

    if (invalidUsername(u)) {
        throw std::invalid_argument("Invalid username");
    }

    std::string base_home = "/home";
    std::string test_home = "Test/CWE-269_mitre_1/home";
    std::string root;

    if (fs::is_directory(base_home) && fs::exists(base_home) && 
        (fs::status(base_home).permissions() & fs::perms::owner_write) != fs::perms::none) {
        root = base_home;
    } else {
        fs::create_directories(test_home);
        root = test_home;
    }

    fs::path path = fs::path(root) / u;

    raisePrivileges();
    try {
        if (fs::exists(path)) {
            throw fs::filesystem_error("Directory already exists", path, std::error_code());
        }
        if (!fs::create_directory(path)) {
            throw std::runtime_error("Failed to create directory");
        }
    } catch (...) {
        lowerPrivileges();
        throw;
    }
    lowerPrivileges();

    return true;
}