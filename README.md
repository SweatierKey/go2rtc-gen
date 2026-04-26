# go2rtc-gen

Generate a [go2rtc](https://github.com/AlexxIT/go2rtc) `go2rtc.yaml`
configuration from a list of RTSP URLs read on stdin.

## Demo

[![asciicast](https://asciinema.org/a/D1gmXkKO4Do7WO8c.svg)](https://asciinema.org/a/D1gmXkKO4Do7WO8c)

## Install

    chmod +x go2rtc-gen
    cp go2rtc-gen ~/.local/bin/    # or /usr/local/bin/

No dependencies. Pure Python stdlib.

## Usage

Two RTSP URLs from a here-document, default settings:

    go2rtc-gen <<EOF
    rtsp://192.168.1.64:554/Streaming/Channels/101
    rtsp://192.168.1.65:554/Streaming/Channels/101
    EOF

Pipe from `onvif-rtsp` (one URL per line — see the chain below) and write to a
file, customising the stream-name prefix:

    onvif-discover \
      | xargs -I{} onvif-rtsp --user admin --password segreta {} \
      | go2rtc-gen --name-prefix cam -o ~/go2rtc.yaml

Bind go2rtc to non-default addresses:

    go2rtc-gen --api-listen 0.0.0.0:1984 --rtsp-listen 0.0.0.0:8554 < urls.txt

### Output

    api:
      listen: ":1984"
    rtsp:
      listen: ":8554"
    streams:
      cam1: rtsp://192.168.1.64:554/Streaming/Channels/101
      cam2: rtsp://192.168.1.65:554/Streaming/Channels/101

The order of streams reflects the arrival order on stdin. URLs containing
characters reserved by YAML (`@`, `#`, `&`, `*`, `!`, etc.) are emitted as
double-quoted scalars; plain ones are not quoted.

### Flags

| Flag | Default | Meaning |
|---|---|---|
| `--name-prefix PREFIX` | `cam` | stream name prefix; entries become `PREFIX1`, `PREFIX2`, ... |
| `--api-listen ADDR` | `:1984` | go2rtc `api.listen` address |
| `--rtsp-listen ADDR` | `:8554` | go2rtc `rtsp.listen` address |
| `-o`, `--output FILE` | stdout | write the YAML to FILE instead of stdout |
| `-v`, `--verbose` | off | log progress on stderr |
| `-V`, `--version` | | print version and exit |
| `-h`, `--help` | | show help and exit |

### Input rules

- Blank lines on stdin are silently skipped.
- Lines that do not start with `rtsp://` (case-insensitive) are skipped with a
  warning on stderr; the script still exits 0 if at least one valid URL was
  collected.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success (at least one valid URL processed) |
| 1 | usage error (bad flag, unwritable `-o`) |
| 4 | stdin was empty, or every line on stdin was rejected |
| 130 | interrupted with Ctrl-C |

## Dependencies

- Python 3.8+ (stdlib only — no `pyyaml`, no third-party packages)

## Place in the chain

`go2rtc-gen` consumes the output of `onvif-rtsp` (RTSP URLs, one per line) and
produces a configuration file fed into go2rtc:

    onvif-discover → onvif-rtsp → go2rtc-gen → rtsp-play / rtsp-record → footage-merge
