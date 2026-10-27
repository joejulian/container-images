# UniFi Network

Rootless startup for the maintained LinuxServer application/JRE image. The
upstream tag and digest are owned by Renovate's Dockerfile manager. The
published application version is read from the upstream build metadata.

The image runs as UID/GID 999, starts Java directly, and needs a writable
`/unifi` volume and `/tmp`. It does not need capabilities or a service-account
token. `/unifi/data`, `/unifi/log`, and `/unifi/run` preserve the traditional
controller layout. Other settings in `system.properties` are retained.

The default database is a separate MongoDB process bound to loopback port
27117 in the same pod. It is not published by a Service. Remote database
users can supply `MONGO_URI`, `MONGO_STAT_URI`, and `MONGO_DBNAME` through
Secret-backed environment variables. `JVM_MAX_HEAP_SIZE` defaults to 1024M.

Migrate legacy MongoDB through a tested logical restore into fresh storage;
never open an older WiredTiger database directly with a new major version.
The MongoDB mirror's version pattern retains the supported 8.0 release line.
