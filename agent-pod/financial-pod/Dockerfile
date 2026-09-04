FROM golang:1.21-bullseye AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=1 go build -o /app/bin/financialpod ./cmd/financialpod/

FROM debian:bullseye-slim
RUN apt-get update && apt-get install -y ca-certificates sqlite3 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/bin/financialpod /usr/local/bin/financialpod

ENTRYPOINT ["financialpod"]
