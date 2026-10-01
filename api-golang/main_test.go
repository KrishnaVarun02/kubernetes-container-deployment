package main

import (
	"context"
	"errors"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestRoutes(t *testing.T) {
	for _, fail := range []bool{false, true} {
		h := handler(func(context.Context) (time.Time, error) {
			if fail {
				return time.Time{}, errors.New("secret")
			}
			return time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC), nil
		})
		for _, path := range []string{"/", "/ping"} {
			w := httptest.NewRecorder()
			h.ServeHTTP(w, httptest.NewRequest("GET", path, nil))
			want := 200
			if fail {
				want = 503
			}
			if w.Code != want {
				t.Fatalf("status %d", w.Code)
			}
			if strings.Contains(w.Body.String(), "secret") {
				t.Fatal("leaked error")
			}
			if path == "/" && !fail && !strings.Contains(w.Body.String(), `"api":"golang"`) {
				t.Fatal(w.Body.String())
			}
		}
	}
}
