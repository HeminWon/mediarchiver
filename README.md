# mediarchiver

Media archive and rename CLI for regular camera, phone, and sidecar files.

## Download

Download the latest binary from GitHub Releases:

```text
https://github.com/heminwon/mediarchiver/releases
```

Choose the asset for your platform:

```text
mediarchiver-darwin-arm64.tar.gz
mediarchiver-linux-x86_64.tar.gz
```

Then unpack and put `mediarchiver` somewhere in your `PATH`.

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
