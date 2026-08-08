from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from android_update_server.server import RepositoryConfig, make_server


class UpdateServerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.policy_directory = tempfile.TemporaryDirectory()
        self.token = "t" * 48
        config = RepositoryConfig(
            Path(self.temporary_directory.name),
            self.token,
            1024 * 1024,
            Path(self.policy_directory.name),
        )
        config.prepare()
        self.server = make_server(config, "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary_directory.cleanup()
        self.policy_directory.cleanup()

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
    ):
        request = Request(self.base_url + path, data=body, method=method, headers=headers or {})
        return urlopen(request, timeout=2)

    def publish_artifact(self, name: str, content: bytes) -> None:
        with self.request(
            f"/admin/v1/artifacts/{name}",
            method="PUT",
            body=content,
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Checksum-Sha256": hashlib.sha256(content).hexdigest(),
            },
        ) as response:
            self.assertEqual(response.status, 201)

    def test_health(self) -> None:
        with self.request("/healthz") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response), {"status": "ok"})

    def test_artifacts_are_authenticated_immutable_and_range_capable(self) -> None:
        content = b"0123456789"
        with self.assertRaises(HTTPError) as context:
            self.request(
                "/admin/v1/artifacts/release.zip",
                method="PUT",
                body=content,
                headers={"X-Checksum-Sha256": hashlib.sha256(content).hexdigest()},
            )
        self.assertEqual(context.exception.code, 401)
        self.assertEqual(context.exception.headers["Connection"], "close")
        context.exception.close()

        self.publish_artifact("rock4se/release.zip", content)

        with self.assertRaises(HTTPError) as context:
            self.publish_artifact("rock4se/release.zip", content)
        self.assertEqual(context.exception.code, 409)
        context.exception.close()

        with self.request(
            "/artifacts/rock4se/release.zip", headers={"Range": "bytes=2-5"}
        ) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"2345")
            self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")

    def test_channel_publication_and_validation(self) -> None:
        artifact = b"apk"
        digest = hashlib.sha256(artifact).hexdigest()
        self.publish_artifact("apps/home-assistant.apk", artifact)
        manifest = {
            "schemaVersion": 1,
            "device": "rock4se",
            "channel": "stable",
            "applications": [
                {
                    "package": "io.homeassistant.companion.android.minimal",
                    "version": "2026.6.5",
                    "versionCode": 22884,
                    "url": "/artifacts/apps/home-assistant.apk",
                    "sha256": digest,
                    "size": len(artifact),
                }
            ],
        }
        body = json.dumps(manifest).encode()
        with self.request(
            "/admin/v1/channels/rock4se/stable",
            method="PUT",
            body=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
        ) as response:
            self.assertEqual(response.status, 201)

        with self.request("/v1/channels/rock4se/stable") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response), manifest)

        invalid_manifest = dict(manifest, device="rock4plus")
        with self.assertRaises(HTTPError) as context:
            self.request(
                "/admin/v1/channels/rock4se/stable",
                method="PUT",
                body=json.dumps(invalid_manifest).encode(),
                headers={"Authorization": f"Bearer {self.token}"},
            )
        self.assertEqual(context.exception.code, 422)
        context.exception.close()

    def test_device_policy_is_public_and_read_only(self) -> None:
        policy = {
            "schemaVersion": 1,
            "device": "rock4se",
            "requiredPackages": ["com.duckduckgo.mobile.android"],
        }
        policy_path = Path(self.policy_directory.name) / "rock4se.json"
        policy_path.write_text(json.dumps(policy), encoding="utf-8")

        with self.request("/v1/policies/rock4se") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response), policy)

        with self.assertRaises(HTTPError) as context:
            self.request("/v1/policies/../secret")
        self.assertEqual(context.exception.code, 404)
        context.exception.close()


if __name__ == "__main__":
    unittest.main()
