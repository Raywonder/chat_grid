#!/bin/sh
set -eu
key=/tmp/raywonder-codex
trap 'rm -f "$key"' EXIT
install -m 600 /mnt/c/Users/40493/.ssh/raywonder "$key"
rsync -av --exclude '.venv*' --exclude 'build' --exclude 'dist' --exclude 'release' \
  -e "ssh -i $key -p 450 -o IdentitiesOnly=yes -o BatchMode=yes" \
  /mnt/c/Users/40493/git/.codex-work/chatgrid-native-layout/ \
  tappedin@64.20.46.178:/home/tappedin/tmp/chatgrid-native-layout/
