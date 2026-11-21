#!/usr/bin/env bash
# Production deploy: update the code from main and rebuild / restart the stack.
#
# Runs on the server. GitHub Actions calls it over SSH with a deploy key that
# is allowed to run only this script (forced command in ~/.ssh/authorized_keys).
# Manual run on the server:  bash ~/online-cinema-service/deploy.sh

set -euo pipefail

compose() {
    docker compose -f docker-compose.prod.yaml "$@"
}

# The whole script is one function: bash reads it completely before running,
# so `git pull` replacing this file mid-run cannot break the current deploy.
main() {
    cd "$(dirname "$0")"

    echo "==> Pulling main"
    git pull --ff-only origin main
    git log -1 --oneline

    # One image at a time: building both in parallel may run out of 1 GB RAM.
    echo "==> Building backend image"
    compose build web
    echo "==> Building frontend / nginx image"
    compose build nginx

    # --build: migrate / worker / beat use the same Dockerfile as web —
    # rebuilt from cache in seconds, otherwise they would keep the old code.
    echo "==> Starting the stack (migrations run first)"
    compose up -d --build

    echo "==> Removing old images"
    docker image prune -f

    compose ps
    echo "==> Deploy finished"
}

main "$@"
exit
