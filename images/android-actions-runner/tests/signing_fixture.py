#!/usr/bin/env python3
"""Exercise APK v3 rotation with disposable keys before publishing a runner."""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile


def run(*args):
    result = subprocess.run([str(arg) for arg in args], capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(f"{Path(args[0]).name} failed (output withheld)")
    return result.stdout


def main():
    os.umask(0o077)
    sdk = Path(os.environ.get("ANDROID_SDK_ROOT", "/opt/android-sdk"))
    version = os.environ["ANDROID_BUILD_TOOLS_VERSION"]
    tools = sdk / "build-tools" / version
    signer = tools / "apksigner"
    root = Path("/tmp/jjulian")
    root.mkdir(mode=0o700, exist_ok=True)
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise RuntimeError("temporary signing directory must be owned and private")
    with tempfile.TemporaryDirectory(prefix="runner-signing-", dir=root) as directory:
        temp = Path(directory)
        password = temp / "password"
        password.write_text("dummy-fixture-password\n")
        successor_password = temp / "successor-password"
        successor_password.write_text("dummy-fixture-password\n")
        certificates = []
        for name in ("original", "successor"):
            key = temp / f"{name}.p12"
            run("keytool", "-genkeypair", "-noprompt", "-alias", "fixture",
                "-keyalg", "RSA", "-keysize", "2048", "-validity", "2",
                "-dname", f"CN={name},O=Example Fixture,C=US", "-keystore", key,
                "-storepass:file", password, "-keypass:file", password)
            certificate = run("keytool", "-exportcert", "-alias", "fixture",
                              "-keystore", key, "-storepass:file", password)
            certificates.append(hashlib.sha256(certificate).hexdigest())
        lineage = temp / "rotation.lineage"
        run(signer, "rotate", "--out", lineage, "--old-signer",
            "--ks", temp / "original.p12", "--ks-key-alias", "fixture",
            "--ks-pass", f"file:{password}", "--set-installed-data", "true",
            "--set-shared-uid", "false", "--set-permission", "false",
            "--set-rollback", "false", "--set-auth", "false", "--new-signer",
            "--ks", temp / "successor.p12", "--ks-key-alias", "fixture",
            "--ks-pass", f"file:{successor_password}")
        manifest = temp / "AndroidManifest.xml"
        manifest.write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    package="invalid.example.runnerfixture">
    <uses-sdk android:minSdkVersion="28" android:targetSdkVersion="35" />
    <application android:label="Signing fixture" />
</manifest>''')
        unsigned, signed = temp / "unsigned.apk", temp / "signed.apk"
        run(tools / "aapt2", "link", "-o", unsigned, "--manifest", manifest,
            "-I", sdk / "platforms/android-35/android.jar")
        run(signer, "sign", "--ks", temp / "successor.p12", "--ks-key-alias",
            "fixture", "--ks-pass", f"file:{password}", "--lineage", lineage,
            "--min-sdk-version", "28", "--rotation-min-sdk-version", "28",
            "--v1-signing-enabled", "false", "--v2-signing-enabled", "false",
            "--v3-signing-enabled", "true", "--v4-signing-enabled", "false",
            "--out", signed, unsigned)
        verification = run(signer, "verify", "--min-sdk-version", "28",
                           "--verbose", "--print-certs", signed).decode()
        for expected in (
            "Verified using v1 scheme (JAR signing): false",
            "Verified using v2 scheme (APK Signature Scheme v2): false",
            "Verified using v3 scheme (APK Signature Scheme v3): true",
            "Number of signers: 1",
        ):
            if expected not in verification.splitlines():
                raise RuntimeError(f"signature scheme check failed: {expected}")
        current = re.findall(r"^V3\.0 Signer: certificate SHA-256 digest: (.+)$",
                             verification, re.MULTILINE)
        if current != [certificates[1]]:
            raise RuntimeError("SDK must report exactly the successor v3 signer")
        history = run(signer, "lineage", "--in", signed, "--print-certs").decode()
        digests = re.findall(r"^Signer #\d+ in lineage certificate SHA-256 digest: (.+)$",
                             history, re.MULTILINE)
        if digests != certificates:
            raise RuntimeError("signing lineage must retain original-to-successor order")
        original = history.split("Signer #2 in lineage", 1)[0]
        for capability, value in (("installed data", "true"), ("shared UID", "false"),
                                  ("permission", "false"), ("rollback", "false"),
                                  ("auth", "false")):
            pattern = rf"^Has {capability} capability\s*: {value}$"
            if not re.search(pattern, original, re.MULTILINE):
                raise RuntimeError(f"incorrect original certificate capability: {capability}")
    print("APK v3 signing, rotation order, and restricted capabilities verified")


if __name__ == "__main__":
    main()
