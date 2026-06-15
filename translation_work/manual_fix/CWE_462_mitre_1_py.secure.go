package main

import (
	"errors"
	"sort"
)

func foo() (string, string) {
	return "./", "file.txt"
}

func dataSorting() [][2]string {
	alist := make([][2]string, 0)
	seen := make(map[[2]string]bool)

	limit := 64
	for i := 0; i < limit; i++ {
		basename, data := foo()
		if basename == "" || data == "" {
			break
		}
		key := [2]string{basename, data}
		if seen[key] {
			panic(errors.New("value error"))
		}
		seen[key] = true
		alist = append(alist, key)
		sort.Slice(alist, func(i, j int) bool {
			if alist[i][0] != alist[j][0] {
				return alist[i][0] < alist[j][0]
			}
			return alist[i][1] < alist[j][1]
		})
	}
	if len(alist) == limit {
		panic(errors.New("runtime error"))
	}

	return alist
}