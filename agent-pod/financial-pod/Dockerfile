FROM golang:1.21-bullseye AS builder

WORKDIR /app

# Initialize go module if it doesn't exist
RUN go mod init github.com/kuberbolt/gatekeeper || true
RUN go get google.golang.org/grpc

COPY fp/ /app/fp/
# In a real scenario, copy protos and generate them here
# COPY proto/ /app/proto/

# Build
RUN go build -o /app/bin/fp ./fp/main.go

FROM debian:bullseye-slim

WORKDIR /app
COPY --from=builder /app/bin/fp /usr/local/bin/fp

CMD ["fp"]
