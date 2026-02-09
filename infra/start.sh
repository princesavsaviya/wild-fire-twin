#!/usr/bin/env bash
set -e

if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC="docker compose"
fi

$DC -f infra/docker-compose.yml pull
$DC -f infra/docker-compose.yml up -d
$DC -f infra/docker-compose.yml ps
