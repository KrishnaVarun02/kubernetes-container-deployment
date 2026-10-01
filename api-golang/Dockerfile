FROM golang:1.24.4-alpine3.22 AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 go build -trimpath -o /api .
FROM alpine:3.22.0
RUN adduser -D -u 10001 app
COPY --from=build /api /api
USER app
EXPOSE 8080
ENTRYPOINT ["/api"]
