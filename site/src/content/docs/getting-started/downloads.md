---
title: Downloads
description: Download the DiskGOup CLI binary or the desktop app for macOS, Linux and Windows.
---

Every release ships a standalone CLI binary and a desktop app, built by the
project's own CI and attached to the
[GitHub release](https://github.com/elshadaghazade/diskgoup/releases) of the
tag.

<!-- release:start -->
**Latest release: `v0.4.1`** · [the release notes →](https://github.com/elshadaghazade/diskgoup/releases/tag/v0.4.1)
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

The app bundles the CLI, so every build is self-contained — it does not
need Python on the target machine. Two kinds are published for each
platform: the **installer**, and the **portable** copy, which needs no
installation at all.

| Platform | Architecture | Format | Download | How to run it |
|---|---|---|---|---|
| macOS | Apple silicon (arm64) | Installer | [`DiskGOup-macOS-arm64.dmg`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-macOS-arm64.dmg) | double-click it, then drag `DiskGOup.app` into Applications |
| macOS | Intel (x64) | Installer | [`DiskGOup-macOS-x64.dmg`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-macOS-x64.dmg) | double-click it, then drag `DiskGOup.app` into Applications |
| macOS | Apple silicon (arm64) | Portable | [`DiskGOup-macOS-arm64.zip`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-macOS-arm64.zip) | unzip it, then double-click `DiskGOup.app` |
| macOS | Intel (x64) | Portable | [`DiskGOup-macOS-x64.zip`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-macOS-x64.zip) | unzip it, then double-click `DiskGOup.app` |
| Windows | x64 | Installer | [`DiskGOup-Windows-x64.exe`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-Windows-x64.exe) | double-click it and follow the installer |
| Windows | x64 | Portable | [`DiskGOup-Windows-portable-x64.exe`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-Windows-portable-x64.exe) | double-click it — it unpacks itself and runs |
| Linux | x64 | Installer | [`DiskGOup-Linux-x64.AppImage`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-Linux-x64.AppImage) | make it executable, then run it |
| Linux | x64 | Portable | [`DiskGOup-Linux-x64.tar.gz`](https://github.com/elshadaghazade/diskgoup/releases/latest/download/DiskGOup-Linux-x64.tar.gz) | unpack it, then run `./diskgoup-electron` |

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

### The portable builds

The portable rows need no installation: download one, unpack it wherever you
like — a folder, a USB stick — and run it from there.

The macOS app bundle carries its signature inside the archive, so it stays
signed after unzipping and runs from any folder — copy it to a USB stick and
it still works. The Linux archive needs no FUSE, so it also runs where the
AppImage cannot.

:::caution
Being portable does not make the app trusted: Gatekeeper and SmartScreen
check the **code**, not the file it arrives in, so the portable copies are
asked about exactly like the installers — approve them the same way.
:::

## Prefer to build it yourself?

Every download above is built by the
[release workflow](https://github.com/elshadaghazade/diskgoup/blob/main/.github/workflows/release-cli.yml)
from the source in the repository. To build the same binary on your own
machine, see [Building and releasing](/development/building/).

## See also

- [Installation](/getting-started/installation/) — install from source with `uv`.
- [Quick start](/getting-started/quick-start/) — your first scan.
