package main

func foo() (string, string) {
	return "./", "file.txt"
}

func dataSorting() {
	/*
	   Continuously take (basename,data) key-value pair from foo() function and sort it
	*/
	var alist []struct {
		basename string
		data     string
	}
	basename := true
	data := true
	for basename && data {
		basenameStr, dataStr := foo()
		basename = true
		data = true
		alist = append(alist, struct {
			basename string
			data     string
		}{basenameStr, dataStr})
		// Sort the slice
		for i := 0; i < len(alist); i++ {
			for j := i + 1; j < len(alist); j++ {
				if alist[i].basename > alist[j].basename || (alist[i].basename == alist[j].basename && alist[i].data > alist[j].data) {
					alist[i], alist[j] = alist[j], alist[i]
				}
			}
		}
	}
}