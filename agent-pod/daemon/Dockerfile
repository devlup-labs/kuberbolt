FROM golang:1.23-alpine AS builder

WORKDIR /app
COPY . .
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /daemon ./cmd/main.go

FROM alpine:3.20
COPY --from=builder /daemon /daemon
EXPOSE 50051
ENTRYPOINT ["/daemon"]
