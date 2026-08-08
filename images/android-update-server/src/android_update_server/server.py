"""HTTP server for immutable Android artifacts and mutable release channels."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import mimetypes
import os
from pathlib import Path
import re
import signal
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from tempfile import NamedTemporaryFile
from typing import Any
from urllib.parse import unquote, urlsplit

from android_update_server import __version__


LOGGER = logging.getLogger("android-update-server")
NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MANIFEST_LIMIT = 1024 * 1024
COPY_BUFFER_SIZE = 1024 * 1024


class RepositoryConfig:
    """Validated runtime configuration shared by request handlers."""

    def __init__(
        self,
        data_root: Path,
        admin_token: str,
        max_upload_bytes: int,
        policy_root: Path | None = None,
    ):
        self.data_root = data_root.resolve()
        self.artifacts_root = self.data_root / "artifacts"
        self.channels_root = self.data_root / "channels"
        self.admin_token = admin_token
        self.max_upload_bytes = max_upload_bytes
        self.policy_root = policy_root.resolve() if policy_root is not None else None

    def prepare(self) -> None:
        """Create repository directories before accepting requests."""

        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.channels_root.mkdir(parents=True, exist_ok=True)


class UpdateRepositoryHandler(BaseHTTPRequestHandler):
    """Serve release data and accept authenticated atomic publications."""

    protocol_version = "HTTP/1.1"
    server_version = f"AndroidUpdateServer/{__version__}"
    config: RepositoryConfig

    def do_GET(self) -> None:  # noqa: N802
        self._handle_read(send_body=True)

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle_read(send_body=False)

    def do_PUT(self) -> None:  # noqa: N802
        path = self._request_path()
        if not self._authorized():
            self._send_error(HTTPStatus.UNAUTHORIZED, "valid bearer token required")
            return

        artifact_prefix = "/admin/v1/artifacts/"
        channel_prefix = "/admin/v1/channels/"
        if path.startswith(artifact_prefix):
            self._publish_artifact(path[len(artifact_prefix) :])
            return
        if path.startswith(channel_prefix):
            self._publish_channel(path[len(channel_prefix) :])
            return
        self._send_error(HTTPStatus.NOT_FOUND, "unknown endpoint")

    def _handle_read(self, *, send_body: bool) -> None:
        path = self._request_path()
        if path in ("/healthz", "/readyz"):
            writable = os.access(self.config.data_root, os.W_OK)
            status = HTTPStatus.OK if writable else HTTPStatus.SERVICE_UNAVAILABLE
            self._send_json(status, {"status": "ok" if writable else "not-ready"}, send_body)
            return

        artifact_prefix = "/artifacts/"
        channel_prefix = "/v1/channels/"
        policy_prefix = "/v1/policies/"
        if path.startswith(artifact_prefix):
            artifact = self._safe_path(self.config.artifacts_root, path[len(artifact_prefix) :])
            if artifact is None or not artifact.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "artifact not found")
                return
            self._send_file(artifact, send_body=send_body, immutable=True)
            return

        if path.startswith(channel_prefix):
            names = self._channel_names(path[len(channel_prefix) :])
            if names is None:
                self._send_error(HTTPStatus.NOT_FOUND, "channel not found")
                return
            device, channel = names
            manifest = self.config.channels_root / device / f"{channel}.json"
            if not manifest.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "channel not found")
                return
            self._send_file(manifest, send_body=send_body, immutable=False)
            return

        if path.startswith(policy_prefix):
            device = unquote(path[len(policy_prefix) :].strip("/"))
            if (
                self.config.policy_root is None
                or not NAME_PATTERN.fullmatch(device)
            ):
                self._send_error(HTTPStatus.NOT_FOUND, "policy not found")
                return
            policy = self.config.policy_root / f"{device}.json"
            if not policy.is_file():
                self._send_error(HTTPStatus.NOT_FOUND, "policy not found")
                return
            self._send_file(policy, send_body=send_body, immutable=False)
            return

        self._send_error(HTTPStatus.NOT_FOUND, "unknown endpoint")

    def _publish_artifact(self, relative_path: str) -> None:
        destination = self._safe_path(self.config.artifacts_root, relative_path)
        if destination is None:
            self._send_error(HTTPStatus.BAD_REQUEST, "invalid artifact path")
            return
        if destination.exists():
            self._send_error(HTTPStatus.CONFLICT, "artifact already exists")
            return

        expected_digest = self.headers.get("X-Checksum-Sha256", "").lower()
        if not SHA256_PATTERN.fullmatch(expected_digest):
            self._send_error(HTTPStatus.BAD_REQUEST, "X-Checksum-Sha256 is required")
            return

        length = self._content_length(self.config.max_upload_bytes)
        if length is None:
            return

        destination.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        temporary_name: str | None = None
        try:
            with NamedTemporaryFile(
                mode="wb", prefix=".upload-", dir=destination.parent, delete=False
            ) as temporary:
                temporary_name = temporary.name
                remaining = length
                while remaining:
                    chunk = self.rfile.read(min(COPY_BUFFER_SIZE, remaining))
                    if not chunk:
                        raise ConnectionError("request body ended before Content-Length")
                    temporary.write(chunk)
                    digest.update(chunk)
                    remaining -= len(chunk)
                temporary.flush()
                os.fsync(temporary.fileno())

            actual_digest = digest.hexdigest()
            if not hmac.compare_digest(actual_digest, expected_digest):
                self._send_error(HTTPStatus.UNPROCESSABLE_ENTITY, "checksum mismatch")
                return

            try:
                os.link(temporary_name, destination)
            except FileExistsError:
                self._send_error(HTTPStatus.CONFLICT, "artifact already exists")
                return

            self._send_json(
                HTTPStatus.CREATED,
                {
                    "path": f"/artifacts/{relative_path}",
                    "sha256": actual_digest,
                    "size": length,
                },
            )
        except ConnectionError as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

    def _publish_channel(self, suffix: str) -> None:
        names = self._channel_names(suffix)
        if names is None:
            self._send_error(HTTPStatus.BAD_REQUEST, "channel path must be DEVICE/CHANNEL")
            return
        device, channel = names

        length = self._content_length(MANIFEST_LIMIT)
        if length is None:
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self._send_error(HTTPStatus.BAD_REQUEST, "incomplete request body")
            return

        try:
            document = json.loads(body)
            self._validate_manifest(document, device, channel)
        except (json.JSONDecodeError, ValueError) as error:
            self._send_error(HTTPStatus.UNPROCESSABLE_ENTITY, str(error))
            return

        encoded = (json.dumps(document, indent=2, sort_keys=True) + "\n").encode()
        destination = self.config.channels_root / device / f"{channel}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with NamedTemporaryFile(
                mode="wb", prefix=".channel-", dir=destination.parent, delete=False
            ) as temporary:
                temporary_name = temporary.name
                temporary.write(encoded)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_name, destination)
            temporary_name = None
        finally:
            if temporary_name is not None:
                Path(temporary_name).unlink(missing_ok=True)

        self._send_json(
            HTTPStatus.CREATED,
            {
                "channel": channel,
                "device": device,
                "sha256": hashlib.sha256(encoded).hexdigest(),
            },
        )

    @staticmethod
    def _validate_manifest(document: Any, device: str, channel: str) -> None:
        if not isinstance(document, dict):
            raise ValueError("manifest must be a JSON object")
        if document.get("schemaVersion") != 1:
            raise ValueError("schemaVersion must be 1")
        if document.get("device") != device or document.get("channel") != channel:
            raise ValueError("manifest device and channel must match the request path")

        os_release = document.get("os")
        if os_release is not None:
            UpdateRepositoryHandler._validate_release(os_release, "os")

        applications = document.get("applications", [])
        if not isinstance(applications, list):
            raise ValueError("applications must be an array")
        packages: set[str] = set()
        for application in applications:
            UpdateRepositoryHandler._validate_release(application, "application")
            package = application.get("package")
            if not isinstance(package, str) or not package:
                raise ValueError("each application requires a package")
            if package in packages:
                raise ValueError(f"duplicate application package: {package}")
            packages.add(package)
            if not isinstance(application.get("versionCode"), int):
                raise ValueError(f"application {package} requires an integer versionCode")

    @staticmethod
    def _validate_release(release: Any, kind: str) -> None:
        if not isinstance(release, dict):
            raise ValueError(f"{kind} release must be an object")
        if not isinstance(release.get("version"), str) or not release["version"]:
            raise ValueError(f"{kind} release requires a version")
        url = release.get("url")
        if not isinstance(url, str) or not url.startswith("/artifacts/"):
            raise ValueError(f"{kind} release URL must begin with /artifacts/")
        digest = release.get("sha256")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise ValueError(f"{kind} release requires a lowercase SHA-256 digest")
        size = release.get("size")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError(f"{kind} release requires a non-negative integer size")

    def _send_file(self, path: Path, *, send_body: bool, immutable: bool) -> None:
        stat = path.stat()
        start = 0
        end = stat.st_size - 1
        status = HTTPStatus.OK
        range_header = self.headers.get("Range")
        if range_header:
            parsed_range = self._parse_range(range_header, stat.st_size)
            if parsed_range is None:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{stat.st_size}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            start, end = parsed_range
            status = HTTPStatus.PARTIAL_CONTENT

        content_length = max(0, end - start + 1)
        self.send_response(status)
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("ETag", f'"{stat.st_mtime_ns:x}-{stat.st_size:x}"')
        self.send_header(
            "Cache-Control",
            "public, max-age=31536000, immutable" if immutable else "no-cache",
        )
        if status == HTTPStatus.PARTIAL_CONTENT:
            self.send_header("Content-Range", f"bytes {start}-{end}/{stat.st_size}")
        self.end_headers()
        if not send_body or content_length == 0:
            return

        with path.open("rb") as source:
            source.seek(start)
            remaining = content_length
            while remaining:
                chunk = source.read(min(COPY_BUFFER_SIZE, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    @staticmethod
    def _parse_range(header: str, size: int) -> tuple[int, int] | None:
        if not header.startswith("bytes=") or "," in header or size == 0:
            return None
        bounds = header[6:].split("-", 1)
        if len(bounds) != 2:
            return None
        try:
            if bounds[0] == "":
                suffix = int(bounds[1])
                if suffix <= 0:
                    return None
                return max(0, size - suffix), size - 1
            start = int(bounds[0])
            end = int(bounds[1]) if bounds[1] else size - 1
        except ValueError:
            return None
        if start < 0 or start >= size or end < start:
            return None
        return start, min(end, size - 1)

    def _authorized(self) -> bool:
        prefix = "Bearer "
        header = self.headers.get("Authorization", "")
        return header.startswith(prefix) and hmac.compare_digest(
            header[len(prefix) :], self.config.admin_token
        )

    def _content_length(self, limit: int) -> int | None:
        raw_length = self.headers.get("Content-Length")
        try:
            length = int(raw_length) if raw_length is not None else -1
        except ValueError:
            length = -1
        if length < 0:
            self._send_error(HTTPStatus.LENGTH_REQUIRED, "valid Content-Length required")
            return None
        if length > limit:
            self._send_error(HTTPStatus.CONTENT_TOO_LARGE, "request body too large")
            return None
        return length

    @staticmethod
    def _safe_path(root: Path, suffix: str) -> Path | None:
        decoded = unquote(suffix)
        if not decoded or "\\" in decoded or "\x00" in decoded:
            return None
        candidate = (root / decoded).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            return None
        return candidate

    @staticmethod
    def _channel_names(suffix: str) -> tuple[str, str] | None:
        parts = [unquote(part) for part in suffix.strip("/").split("/")]
        if len(parts) != 2 or not all(NAME_PATTERN.fullmatch(part) for part in parts):
            return None
        return parts[0], parts[1]

    def _request_path(self) -> str:
        return urlsplit(self.path).path

    def _send_json(
        self, status: HTTPStatus, document: dict[str, Any], send_body: bool = True
    ) -> None:
        body = (json.dumps(document, separators=(",", ":")) + "\n").encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if send_body:
            self.wfile.write(body)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        self._send_json(status, {"error": message})

    def log_message(self, message_format: str, *args: Any) -> None:
        LOGGER.info(
            "%s - %s",
            self.client_address[0],
            message_format % args,
        )


def make_server(config: RepositoryConfig, host: str, port: int) -> ThreadingHTTPServer:
    """Construct a configured HTTP server."""

    handler = type(
        "ConfiguredUpdateRepositoryHandler",
        (UpdateRepositoryHandler,),
        {"config": config},
    )
    return ThreadingHTTPServer((host, port), handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")))
    parser.add_argument(
        "--data-root", type=Path, default=Path(os.environ.get("DATA_ROOT", "/data"))
    )
    parser.add_argument(
        "--admin-token-file",
        type=Path,
        default=Path(os.environ.get("ADMIN_TOKEN_FILE", "/run/secrets/admin-token")),
    )
    parser.add_argument(
        "--max-upload-bytes",
        type=int,
        default=int(os.environ.get("MAX_UPLOAD_BYTES", str(8 * 1024**3))),
    )
    parser.add_argument(
        "--policy-root",
        type=Path,
        default=(
            Path(os.environ["POLICY_ROOT"])
            if os.environ.get("POLICY_ROOT")
            else None
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    admin_token = args.admin_token_file.read_text(encoding="utf-8").strip()
    if len(admin_token) < 32:
        raise SystemExit("admin token must contain at least 32 characters")

    config = RepositoryConfig(
        args.data_root,
        admin_token,
        args.max_upload_bytes,
        args.policy_root,
    )
    config.prepare()
    server = make_server(config, args.host, args.port)

    def stop_server(_signum: int, _frame: Any) -> None:
        LOGGER.info("shutdown requested")
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop_server)
    signal.signal(signal.SIGINT, stop_server)
    LOGGER.info("listening on %s:%d", args.host, server.server_port)
    server.serve_forever()


if __name__ == "__main__":
    main()
