# Android update server

This image serves immutable Android OTA/APK artifacts and mutable per-device
release-channel manifests from a persistent volume.

Public endpoints:

- `GET /healthz` and `GET /readyz`
- `GET /v1/channels/{device}/{channel}`
- `GET /v1/policies/{device}` when a read-only policy directory is configured
- `GET /artifacts/{path}` with HTTP range support

Publishing endpoints require `Authorization: Bearer ...`:

- `PUT /admin/v1/artifacts/{path}` with `X-Checksum-Sha256`
- `PUT /admin/v1/channels/{device}/{channel}` with a schema-version 1 manifest

Artifact names are immutable. Channel documents are atomically replaceable
pointers to signed Android OTA packages and developer-signed APKs.

Set `POLICY_ROOT` to expose GitOps-managed device policies separately from the
mutable release data on the persistent volume.
