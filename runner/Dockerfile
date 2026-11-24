# PeakCV code runner. Deployed on Railway as its own service with Root Directory = runner.
FROM python:3.11-slim-bookworm

# Compilers and runtimes for the six coding-round languages (Python comes with the image).
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc g++ libc6-dev nodejs default-jdk-headless golang-go \
    && rm -rf /var/lib/apt/lists/*

# Submitted code runs as this unprivileged user, never as the server's user.
RUN useradd --uid 10001 --create-home --shell /usr/sbin/nologin sandbox \
    && mkdir -p /var/cache/go-build && chown sandbox:sandbox /var/cache/go-build \
    # Pre-build Go's standard library so each Go submission compiles in about a second.
    && su -s /bin/sh -c 'GOCACHE=/var/cache/go-build HOME=/tmp GO111MODULE=off go build std' sandbox

WORKDIR /app
COPY server.py .

ENV PYTHONUNBUFFERED=1 PORT=8080 GOCACHE_DIR=/var/cache/go-build
EXPOSE 8080

# Runs as root only to switch each submission to the sandbox user.
CMD ["python", "server.py"]
