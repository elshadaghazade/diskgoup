---
title: Downloads
description: Download the DiskGOup CLI binary or the desktop app for macOS, Linux and Windows.
---

Every release ships a standalone CLI binary and a desktop app, built by the
project's own CI and attached to the
[GitHub release](https://github.com/elshadaghazade/diskgoup/releases) of the
tag.

<!-- release:start -->
**Latest release: `v0.2.0`** · [the release notes →](https://github.com/elshadaghazade/diskgoup/releases/tag/v0.2.0)
<!-- release:end -->

The links below always point at the **newest** release — there is nothing to
update when a new version comes out.

## The CLI

One self-contained binary. It needs no Python and no installation.

| Platform | Architecture | Download |
|---|---|---|
| macOS | Apple silicon (arm64) | [`diskgoup-cli-macos-arm64.tar.gz`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/diskgoup-cli-macos-arm64.tar.gz) |
| macOS | Intel (x64) | [`diskgoup-cli-macos-x64.tar.gz`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/diskgoup-cli-macos-x64.tar.gz) |
| Linux | x64 | [`diskgoup-cli-linux-x64.tar.gz`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/diskgoup-cli-linux-x64.tar.gz) |
| Linux | arm64 | [`diskgoup-cli-linux-arm64.tar.gz`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/diskgoup-cli-linux-arm64.tar.gz) |
| Windows | x64 | [`diskgoup-cli-windows-x64.zip`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/diskgoup-cli-windows-x64.zip) |

After downloading:

```bash
tar -xzf diskgoup-cli-linux-x64.tar.gz   # → diskgoup
chmod +x diskgoup
./diskgoup --version
```

On Windows, unzip the archive and run `diskgoup.exe`.

Every release also carries a `checksums-cli.txt` with the SHA-256 of each
file, so you can verify what you downloaded:

```bash
sha256sum --check checksums-cli.txt
```

## The desktop app

The app bundles the CLI, so the installer is self-contained — it does not
need Python on the target machine.

| Platform | Architecture | Download |
|---|---|---|
| macOS | Apple silicon (arm64) | [`DiskGOup-macOS-arm64.dmg`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-macOS-arm64.dmg) |
| macOS | Intel (x64) | [`DiskGOup-macOS-x64.dmg`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-macOS-x64.dmg) |
| Windows | x64 | [`DiskGOup-Windows-x64.exe`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-Windows-x64.exe) |
| Linux | x64 | [`DiskGOup-Linux-x64.AppImage`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-Linux-x64.AppImage) |

:::caution
The macOS build is signed, but with an **ad-hoc** signature rather than a
Developer ID, so it is not notarized and Gatekeeper asks you to approve it on
the first launch: **System Settings → Privacy & Security → Open Anyway**, then
**Open** — [Apple's own route](https://support.apple.com/en-us/102445).

The Windows build is unsigned, so SmartScreen may warn about it.
:::

On Linux, make the AppImage executable before running it:

```bash
chmod +x DiskGOup-Linux-x64.AppImage
./DiskGOup-Linux-x64.AppImage
```

## Prefer to build it yourself?

Every download above is built by the
[release workflow](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release-cli.yml)
from the source in the repository. To build the same binary on your own
machine, see [Building and releasing](/development/building/).

## See also

- [Installation](/getting-started/installation/) — install from source with `uv`.
- [Quick start](/getting-started/quick-start/) — your first scan.
