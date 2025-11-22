package main

import (
	"log"
	"os"

	"github.com/internet-measurement-network/dbos/internal/server"
)

func main() {
	// Get configuration from environment variables
	redisAddr := os.Getenv("REDIS_ADDR")
	if redisAddr == "" {
		redisAddr = "localhost:6379"
	}

	port := os.Getenv("PORT")
	if port == "" {
		port = "50051"
	}

	// Create and start the server
	srv := server.NewServer(redisAddr)

	log.Printf("Starting DBOS server on port %s with Redis at %s", port, redisAddr)
	if err := srv.Start(port); err != nil {
		log.Fatalf("Failed to start server: %v", err)
	}
}
