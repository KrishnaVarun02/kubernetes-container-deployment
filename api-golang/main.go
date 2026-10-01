package main

import (
	"context"
	"encoding/json"
	"fmt"
	"github.com/jackc/pgx/v5/pgxpool"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"
)

type clockDB func(context.Context) (time.Time, error)

func handler(now clockDB) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		t, err := now(ctx)
		w.Header().Set("Content-Type", "application/json")
		if err != nil {
			w.WriteHeader(503)
			fmt.Fprintln(w, `{"error":"database unavailable"}`)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"api": "golang", "now": t})
	})
	mux.HandleFunc("GET /ping", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		if _, err := now(ctx); err != nil {
			http.Error(w, "database unavailable", 503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintln(w, `"pong"`)
	})
	return mux
}
func main() {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" && os.Getenv("DATABASE_URL_FILE") != "" {
		b, e := os.ReadFile(os.Getenv("DATABASE_URL_FILE"))
		if e != nil {
			log.Fatal("Cannot read database URL file")
		}
		dsn = strings.TrimSpace(string(b))
	}
	if dsn == "" {
		log.Fatal("Set DATABASE_URL or DATABASE_URL_FILE")
	}
	db, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		log.Fatal("Invalid database configuration")
	}
	defer db.Close()
	now := func(ctx context.Context) (time.Time, error) {
		var t time.Time
		err := db.QueryRow(ctx, "SELECT NOW() AS now").Scan(&t)
		return t, err
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}
	server := &http.Server{Addr: ":" + port, Handler: handler(now), ReadHeaderTimeout: 5 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		end, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(end)
	}()
	log.Println("Go API ready on", port)
	if err = server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
}
