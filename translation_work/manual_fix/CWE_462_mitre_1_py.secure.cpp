#include <iostream>
#include <vector>
#include <string>
#include <tuple>
#include <algorithm>
#include <set>

std::tuple<std::string, std::string> foo() {
    return std::make_tuple("./", "file.txt");
}

std::vector<std::tuple<std::string, std::string>> dataSorting() {
    std::vector<std::tuple<std::string, std::string>> alist;
    std::set<std::tuple<std::string, std::string>> seen;

    const int limit = 64;
    bool loop_completed = false;
    for (int i = 0; i < limit; ++i) {
        auto pair = foo();
        if (std::tuple_size<decltype(pair)>::value != 2) {
            throw std::runtime_error("TypeError");
        }
        auto basename = std::get<0>(pair);
        auto data = std::get<1>(pair);
        if (basename.empty() || data.empty()) {
            break;
        }
        auto key = std::make_tuple(basename, data);
        if (seen.find(key) != seen.end()) {
            throw std::runtime_error("ValueError");
        }
        seen.insert(key);
        alist.push_back(key);
        std::sort(alist.begin(), alist.end());
        loop_completed = true;
    }
    
    if (loop_completed) {
        throw std::runtime_error("RuntimeError");
    }

    return alist;
}