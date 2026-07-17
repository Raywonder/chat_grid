#!/usr/bin/env bash
set -euo pipefail

env_file=/etc/asterisk/clawdia-pbx.env
out_dir=/home/tappedin/.openclaw/workspace/projects/chat_grid/client/public/sounds/human
install -d -m 0755 "$out_dir"

api_key=$(sed -n 's/^ELEVENLABS_API_KEY=//p' "$env_file" | head -n1 | tr -d '\r' | sed 's/^"//;s/"$//')
test -n "$api_key"

generate() {
  local name=$1
  local prompt=$2
  local duration=$3
  local temporary
  local status
  temporary=$(mktemp)
  status=$(curl -sS -o "$temporary" -w '%{http_code}' \
    -X POST 'https://api.elevenlabs.io/v1/sound-generation' \
    -H "xi-api-key: $api_key" \
    -H 'Content-Type: application/json' \
    -H 'Accept: audio/mpeg' \
    --data "{\"text\":\"$prompt\",\"duration_seconds\":$duration,\"prompt_influence\":0.45}")
  if [[ "$status" != 200 ]]; then
    rm -f "$temporary"
    printf 'Sound generation failed for %s (HTTP %s).\n' "$name" "$status" >&2
    return 1
  fi
  install -m 0644 "$temporary" "$out_dir/$name.mp3"
  rm -f "$temporary"
}

generate gentle-rest-breath 'A very quiet close-mic human resting breath, one slow inhale and soft exhale, relaxed, natural, no speech, no music, no room noise' 3.5
generate sleepy-breath 'A very quiet sleepy human breath, one slow deep inhale and soft warm exhale, peaceful and natural, no snoring, no speech, no music' 4.5
generate bedding-settle 'A person gently settling into a bed, subtle blanket and bedsheet rustle with a tiny mattress creak, intimate quiet bedroom, no speech, no footsteps' 2.5
generate soft-contented-sigh 'A very soft contented human sigh while relaxing in bed, gentle breath only, subtle and natural, no words, no music, no background noise' 2.5
