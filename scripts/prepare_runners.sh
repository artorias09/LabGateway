#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="labgateway-cpp:1"

command -v docker >/dev/null || { echo "Docker não encontrado."; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker não está acessível para este usuário."; exit 1; }

echo "Construindo runner C/C++: $IMAGE"
docker build -t "$IMAGE" -f "$ROOT/docker/cpp.Dockerfile" "$ROOT"
docker image inspect "$IMAGE" >/dev/null
echo "Runner C/C++ pronto."
