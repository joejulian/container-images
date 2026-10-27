#!/bin/sh
set -eu
umask 077
if [ "$#" -gt 0 ]; then
    exec "$@"
fi

mkdir -p /unifi/data /unifi/log /unifi/run/work/ROOT
properties=/unifi/data/system.properties
touch "$properties"
# Keep the existing controller configuration, but make database ownership
# explicit on every start. Never print configuration containing secrets.
awk '!/^(db\.mongo\.local|db\.mongo\.uri|statdb\.mongo\.uri|unifi\.db\.name)=/' \
    "$properties" > "$properties.next"
{
    printf 'db.mongo.local=false\n'
    printf 'db.mongo.uri=%s\n' "${MONGO_URI:-mongodb://127.0.0.1:27117/ace}"
    printf 'statdb.mongo.uri=%s\n' "${MONGO_STAT_URI:-mongodb://127.0.0.1:27117/ace_stat}"
    printf 'unifi.db.name=%s\n' "${MONGO_DBNAME:-ace}"
} >> "$properties.next"
mv "$properties.next" "$properties"

exec java "-Xmx${JVM_MAX_HEAP_SIZE:-1024M}" \
    -Dunifi.datadir=/unifi/data -Dunifi.logdir=/unifi/log \
    -Dunifi.rundir=/unifi/run -Djava.io.tmpdir=/tmp \
    -Djava.awt.headless=true -Dfile.encoding=UTF-8 \
    -Dlog4j2.formatMsgNoLookups=true \
    -XX:+UseParallelGC -XX:+ExitOnOutOfMemoryError \
    --add-opens java.base/java.lang=ALL-UNNAMED \
    --add-opens java.base/java.time=ALL-UNNAMED \
    --add-opens java.base/sun.security.util=ALL-UNNAMED \
    --add-opens java.base/java.io=ALL-UNNAMED \
    --add-opens java.rmi/sun.rmi.transport=ALL-UNNAMED \
    -jar /usr/lib/unifi/lib/ace.jar start
