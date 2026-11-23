#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
: "${DATA_DIR:?DATA_DIR must name the persistent application directory}"
: "${MUSIC_DIR:?MUSIC_DIR must name the music library directory}"
export ND_MUSICFOLDER="$MUSIC_DIR" ND_DATAFOLDER="$DATA_DIR" ND_ADDRESS="${HOST:-0.0.0.0}" ND_PORT="${PORT:-3000}"
export ND_PLUGINS_ENABLED=false ND_ENABLEEXTERNALSERVICES=false ND_ENABLEINSIGHTSCOLLECTOR=false
export ND_LASTFM_ENABLED=false ND_DEEZER_ENABLED=false ND_LISTENBRAINZ_ENABLED=false ND_ENABLEGRAVATAR=false
export ND_SCANNER_SCHEDULE=0 ND_SCANNER_WATCHERWAIT=0 ND_LOGLEVEL=info
exec "$PWD/navidrome" --nobanner
