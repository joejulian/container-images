#!/usr/bin/env bash
set -euo pipefail

test "$(id -u)" -eq 1000
test -w "$CARGO_HOME"
test ! -w "$RUSTUP_HOME"
! command -v docker
node --version
npm --version
python3 -c 'import ssl, tomllib; assert ssl.create_default_context().cert_store_stats()["x509_ca"] > 0'
pkg-config --exists libudev
skopeo --version

work="$(mktemp -d /tmp/rust-actions-smoke.XXXXXXXX)"
cleanup() {
  case "$work" in
    /tmp/rust-actions-smoke.*) rm -r -- "$work" ;;
    *) exit 1 ;;
  esac
}
trap cleanup EXIT
python3 - "$work" <<'PY'
import pathlib, socket, subprocess, sys, tempfile, time
with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
config = pathlib.Path(sys.argv[1]) / "mosquitto.conf"
config.write_text(f"listener {port} 127.0.0.1\nallow_anonymous true\npersistence false\nlog_dest stderr\n")
with tempfile.TemporaryFile() as log:
    broker = subprocess.Popen(["mosquitto", "-c", str(config), "-v"], stdout=log, stderr=log)
    try:
        deadline = time.monotonic() + 10
        while True:
            assert broker.poll() is None, "owned broker exited before readiness"
            log.seek(0)
            output = log.read()
            if f"Opening ipv4 listen socket on port {port}".encode() in output and b" running" in output:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError("owned broker did not report startup")
            time.sleep(0.05)
        address = ["-h", "127.0.0.1", "-p", str(port)]
        subprocess.run(["mosquitto_pub", *address, "-t", "toolchain-smoke", "-m", "toolchain-smoke", "-r"],
                       check=True, timeout=10)
        assert subprocess.check_output(["mosquitto_sub", *address, "-t", "toolchain-smoke", "-C", "1", "-W", "5"],
                                       timeout=10) == b"toolchain-smoke\n"
    finally:
        if broker.poll() is None:
            broker.terminate()
        try:
            broker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            broker.kill()
            broker.wait()
            raise RuntimeError("owned broker did not stop")
PY
mkdir "$work/src"
cat > "$work/Cargo.toml" <<'TOML'
[package]
name = "toolchain-smoke"
version = "0.1.0"
edition = "2024"
TOML
cat > "$work/src/main.rs" <<'RUST'
fn main() {
    println!("toolchain-smoke");
}
RUST
export CARGO_TARGET_DIR="$work/target"
cargo fmt --manifest-path "$work/Cargo.toml" -- --check
cargo clippy --offline --manifest-path "$work/Cargo.toml" -- -D warnings
cargo build --offline --manifest-path "$work/Cargo.toml" --target x86_64-unknown-linux-gnu
test "$("$CARGO_TARGET_DIR/x86_64-unknown-linux-gnu/debug/toolchain-smoke")" = toolchain-smoke
cargo build --offline --manifest-path "$work/Cargo.toml" --target aarch64-unknown-linux-gnu
readelf -h "$CARGO_TARGET_DIR/aarch64-unknown-linux-gnu/debug/toolchain-smoke" | grep -q AArch64
test "$(qemu-aarch64-static -L /usr/aarch64-linux-gnu \
  "$CARGO_TARGET_DIR/aarch64-unknown-linux-gnu/debug/toolchain-smoke")" = toolchain-smoke
printf '%s\n' 'Non-root native/ARM64 compilation, GNU linking and completed ARM64 execution passed'
