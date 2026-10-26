# Patched pgvector/PostgreSQL runtime.
# The upstream image bundles gosu built with an outdated Go standard library.
# Rebuild gosu here and apply current Debian security updates to the runtime.

FROM golang:1.26.9-alpine AS gosu-builder

RUN apk add --no-cache git ca-certificates
RUN git clone --depth 1 --branch 1.20 https://github.com/tianon/gosu.git /src
WORKDIR /src
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/gosu .

FROM pgvector/pgvector:0.8.7-pg18-bookworm

USER root
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gosu-builder /out/gosu /usr/local/bin/gosu
RUN chmod 0755 /usr/local/bin/gosu && gosu --version
