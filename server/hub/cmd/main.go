// FilePath: server/hub/cmd/main.go
package main

import (
	"fmt"
	"log"
	"os"

	tm "github.com/buger/goterm"
	"github.com/itsatony/w4b_v3/server/hub/internal/config"
	"github.com/itsatony/w4b_v3/server/hub/internal/server"
	nuts "github.com/vaudience/go-nuts"
)

func main() {
	// Clear console and draw logo
	ClearConsole()
	DrawLogo()
	// Initialize version info
	nuts.InitVersion()
	nuts.L.Infof("[Main] Starting W4B Hub Server v%s", nuts.GetVersion())

	// Load configuration
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	// Create and start server
	srv := server.New(cfg)
	if err := srv.Start(); err != nil {
		nuts.L.Errorf("[Main] Server error: %v", err)
		os.Exit(1)
	}
}

// ClearConsole clears the console screen and draws the logo.
func ClearConsole() {
	tm.Clear()
	tm.MoveCursor(1, 1)
	tm.Flush()
}

func DrawLogo() {
	fmt.Println()
	lines := []string{
		"    __  ___            __  __      __  ",
		"   / / / (_)   _____  / / / /_  __/ /_ ",
		"  / /_/ / / | / / _ \\/ /_/ / / / / __ \\",
		" / __  / /| |/ /  __/ __  / /_/ / /_/ /",
		"/_/ /_/_/ |___/\\___/_/ /_/\\__,_/_.___/ ",
		"..........................................  " + nuts.GetVersion(),
	}

	for _, line := range lines {
		fmt.Println(line)
	}
}
