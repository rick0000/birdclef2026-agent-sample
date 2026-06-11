#!/bin/bash
set -e

IMAGE_NAME="birdclef2026-tf"

docker build \
  --network=host \
  --build-arg USER_ID="$(id -u)" \
  --build-arg GROUP_ID="$(id -g)" \
  --build-arg USER_NAME="$(id -un)" \
  -f Dockerfile.tensorflow \
  -t "$IMAGE_NAME" .

MEM_LIMIT=$(awk '/MemTotal/{printf "%dg", $2 * 0.8 / 1024 / 1024}' /proc/meminfo)

docker run --gpus all --rm -it \
  --memory="$MEM_LIMIT" \
  -v "$(pwd)":/kaggle \
  "$IMAGE_NAME" \
  /bin/bash
