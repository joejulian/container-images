# Rust Actions toolchain

Generic AMD64 job image for unprivileged Rust CI, including Node for JavaScript
actions, Python, Mosquitto clients/server, Skopeo, and GNU ARM64 cross-compilation.
It contains no Docker client or daemon and requires no host socket or privileged
service. Kubernetes jobs still need externally enforced admission, RBAC and
network restrictions; this image does not provide that boundary itself.

Debian Bookworm preserves the GNU ABI for applications shipped on a Bookworm
runtime. Builds execute on AMD64, including the ARM64 compiler. Static userspace
QEMU is used only to execute completed ARM64 binaries with the installed GNU
sysroot; no host binfmt registration is required.

The default user is UID/GID 1000. The Rust toolchain is installed read-only for
that user, while `CARGO_HOME` is writable. Jobs should put `CARGO_TARGET_DIR` in
their ephemeral workspace or temporary storage. Release outputs should cross
jobs through checked Actions artifacts rather than shared build volumes.

Image builds run `tests/smoke.sh` as the default user: offline native and ARM64
Rust builds, formatting/Clippy, GNU linking and ARM64 execution. The script is
retained at `/usr/local/libexec/rust-actions-smoke` for runtime qualification
under a job's actual security context. Application broker, protocol and hardware
tests remain the consuming project's responsibility.

Immutable versions are derived from the installed Rust and Node versions as
`<rust-version>-node<node-version>`. A tool version change creates a new tag;
distribution-package rebuilds follow the repository's existing `latest` policy.
