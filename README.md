<p align="center">
  <img src="logo.png" alt="mediarchiver logo" width="160">
</p>

<h1 align="center">mediarchiver</h1>

<p align="center">
  Media archive and rename CLI for regular camera, phone, and sidecar files.
</p>

<p align="center">
  <strong>English</strong> | <a href="README.zh-CN.md">中文</a>
</p>

## Who It Is For

- Creators, photographers, and video editors who regularly import mixed files from phones, cameras, and action cameras.
- People who need predictable file names before editing, backup, delivery, or long-term storage.
- Users who keep original camera sidecars such as XML, SRT, LRF, XMP, or similar companion files.
- Anyone who wants a safe preview before batch renaming or archiving real media files.

## What It Solves

- Camera brands and devices generate inconsistent file names.
- Photos, videos, and sidecars are easy to split apart during manual cleanup.
- Large folders are hard to verify before moving into year, quarter, or month archives.
- Batch file operations are risky without a readable preview and explicit apply step.

## Install

The recommended install path is the release wheel with `uv tool install`.
It creates an isolated tool environment and exposes the `mediarchiver` command:

```bash
uv tool install https://github.com/heminwon/mediarchiver/releases/download/v0.1.2/mediarchiver-0.1.2-py3-none-any.whl
```

For local development artifacts:

```bash
uv build
uv tool install --reinstall dist/mediarchiver-*.whl
```

Standalone binaries are also published on GitHub Releases for users who do not
want a Python tool installer:

```text
https://github.com/heminwon/mediarchiver/releases
```

```text
mediarchiver-darwin-arm64.tar.gz
mediarchiver-linux-x86_64.tar.gz
```

Unpack the asset for your platform and put `mediarchiver` somewhere in your `PATH`.

## Requirements

`mediarchiver` reads media metadata through external tools:

```bash
# macOS
brew install exiftool ffmpeg

# Ubuntu / Debian
sudo apt install libimage-exiftool-perl ffmpeg
```

## Usage

Check the installed version:

```bash
mediarchiver --version
```

### Rename

Preview rename results:

```bash
mediarchiver rename <source>
```

Apply ready renames:

```bash
mediarchiver rename <source> --apply
```

List supported rename rules:

```bash
mediarchiver rename --list-rules
```

Write the rename plan to another directory:

```bash
mediarchiver rename <source> --output <dir>
```

### Archive

Preview archive groups:

```bash
mediarchiver archive <source>
```

Archive to another target directory:

```bash
mediarchiver archive <source> --to <target>
```

Choose the date grouping:

```bash
mediarchiver archive <source> --by quarter
mediarchiver archive <source> --by month
mediarchiver archive <source> --by year
```

Apply archive moves:

```bash
mediarchiver archive <source> --apply
```

## Notes

- Commands default to preview mode. Files are changed only when `--apply` is passed.
- Archive ignores system noise such as `.DS_Store`.
- Archive moves recognized sidecar files with their paired media file when possible.

## Documentation

Maintenance notes live in [docs/development.md](docs/development.md).
