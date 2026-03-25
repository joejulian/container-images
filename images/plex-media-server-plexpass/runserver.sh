#!/bin/bash

# Create and tail the log as plex doesn't let us log to stdout/stderr.
PLEX_LOGDIR="${PLEX_MEDIA_SERVER_APPLICATION_SUPPORT_DIR}/Plex Media Server/Logs"
mkdir -p "${PLEX_LOGDIR}"
touch "${PLEX_LOGDIR}/Plex Media Server.log"
tail -F "${PLEX_LOGDIR}/Plex Media Server.log" &

# This is often left behind when a pod is killed. We are always sure we're the only
# instance of the application in this pod.
rm '/config/Library/Application Support/Plex Media Server/plexmediaserver.pid' 2>/dev/null && true

# Run
exec /usr/lib/plexmediaserver/Plex\ Media\ Server &
pid=$!

trap 'kill -SIGTERM $pid; wait $pid' SIGTERM

wait $pid
