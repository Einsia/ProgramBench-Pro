#!/bin/bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1
# The log mount belongs to the host evaluator UID. Keep that ownership so Harbor
# can collect results. The application has a separate UID/GID below.
chmod 700 /tests
# On another host, the bind-mount owner might itself be UID 1001. Preserve host
# ownership for log collection while ensuring the application has a different UID.
pbp_log_uid=$(stat -c %u /logs/verifier)
if [ "$(id -u agent)" = "$pbp_log_uid" ]; then
  pbp_candidate_uid=1002
  while getent passwd "$pbp_candidate_uid" >/dev/null || [ "$pbp_candidate_uid" = "$pbp_log_uid" ]; do
    pbp_candidate_uid=$((pbp_candidate_uid + 1))
  done
  usermod -u "$pbp_candidate_uid" agent
fi
pbp_log_gid=$(stat -c %g /logs/verifier)
if [ "$(id -g agent)" = "$pbp_log_gid" ]; then
  pbp_candidate_gid=1002
  while getent group "$pbp_candidate_gid" >/dev/null; do
    pbp_candidate_gid=$((pbp_candidate_gid + 1))
  done
  groupadd -g "$pbp_candidate_gid" "navidrome-candidate-$pbp_candidate_gid"
  usermod -g "$pbp_candidate_gid" agent
fi
# Inherit the external collector group; the candidate has a different UID/GID.
chmod 2750 /logs/verifier
umask 027
# Prepare trusted roots before any application process starts.
test -d /app && test ! -L /app
chown -h root:root /app
chmod 755 /app
test ! -L /app/candidate-state
mkdir -p /app/candidate-state
chown -h root:root /app/candidate-state
chmod 711 /app/candidate-state
# Driver temporary state is separate from the initially empty application state.
export TMPDIR=/tmp/verifier
# Chromium children may drop DAC capabilities. Use a root-owned private directory
# on the external /tmp bind, not the host-owned, mode-0700 log mount.
mkdir -m 700 -p "$TMPDIR"
chown root:root "$TMPDIR"
# Every episode runs a fresh copy of the solution (the driver copies it and hands the copy to the candidate). The
# original stays root-owned and read-only to the candidate, so nothing written into it reaches the next episode.
if [ -d /app/solution ] && [ ! -L /app/solution ]; then
  chown -hR root:root /app/solution
  chmod -R go-w,ug-s /app/solution
fi
exec python /tests/run.py --state-root /app/candidate-state --out /logs/verifier "$@"
