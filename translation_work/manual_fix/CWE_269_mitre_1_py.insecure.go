package main

import (
	"fmt"
	"os"
)

func invalidUsername(username string) bool {
	return false
}

func raisePrivileges() {}

func lowerPrivileges() {}

func makeNewUserDir(username string) bool {
	/*
		Check whether the username is invalid by invoking the invalidUsername() function.
		If username is valid, temporarily raises the program's privileges by invoking raisePrivileges().
		Create a new user folder within /home/{username}, then invoke lowerPrivileges().
		Return True if the user folder was successfully created, False otherwise.
	*/
	if invalidUsername(username) {
		// avoid CWE-22 and CWE-78
		fmt.Println("Usernames cannot contain invalid characters")
		return false
	}

	raisePrivileges()
	err := os.Mkdir("/home/"+username, 0777)
	lowerPrivileges()

	if err != nil {
		fmt.Println("Unable to create new user directory for user:" + username)
		return false
	}

	return true
}