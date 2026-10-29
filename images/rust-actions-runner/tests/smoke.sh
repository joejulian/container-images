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
mosquitto -h >/dev/null
mosquitto_sub --help >/dev/null

work="$(mktemp -d /tmp/rust-actions-smoke.XXXXXXXX)"
cleanup() {
  case "$work" in
    /tmp/rust-actions-smoke.*) rm -r -- "$work" ;;
    *) exit 1 ;;
  esac
}
trap cleanup EXIT
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
