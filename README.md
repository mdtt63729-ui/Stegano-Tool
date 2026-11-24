# Stegano Tool — Aether OS

A local/offline Termux CLI + localhost web UI for lossless PNG payload storage.
Works on Termux, Linux and macOS with nothing but Python 3.8+ — no third-party
packages.

## Install

```bash
git clone https://github.com/mdtt63729-ui/Stegano-Tool.git
cd Stegano-Tool
chmod +x install.sh
./install.sh
source ~/.bashrc     # or restart the terminal
STEG --version
```

`install.sh` finds your Python 3, installs a `STEG` (and `steg`) launcher and
puts it on PATH for bash, zsh, profile and fish. On Termux it installs into
`$PREFIX/bin`, elsewhere into `~/.local/bin`.

To remove the launcher: `./uninstall.sh`.

## Interactive menu

```bash
STEG
```

Use ↑/↓ and Enter. The app can hide, extract, inspect, remove embedded data and
launch the local web UI. On a terminal without arrow keys (or when stdin is a
pipe) it falls back to a numbered menu, and quits cleanly on EOF.

## Subcommands

```bash
STEG hide    IMAGE PAYLOAD [-o OUT] [-p PASSWORD] [-n NAME]
STEG extract IMAGE [-o FILE|DIR|-] [-p PASSWORD]
STEG inspect IMAGE [--json]
STEG remove  IMAGE [-o OUT]
STEG web     [--host 127.0.0.1] [--port 8080] [--no-browser]
STEG menu
```

`-` means stdin for input and stdout for output, so it works in any shell and
in pipes:

```bash
# embed a file from a pipe
cat secret.zip | STEG hide photo.png - -o out.png

# get the file back on stdout
STEG extract out.png -o - > secret.zip

# password protected, read from a pipe
printf 'hunter2\n' | STEG extract out.png -o - -p -

# inspect without writing anything
STEG inspect out.png --json | jq .size
```

Status messages go to stderr, so `-o -` output stays clean. The password can
also come from the `STEGANO_PASSWORD` environment variable. Exit codes: `0`
success, `1` error, `2` bad usage.

## Web UI

```bash
STEG web
```

Starts `127.0.0.1:8080` and tries to open the Android browser automatically.
Every result has a **Download** link backed by a `/download/<token>` route, so
files produced by the browser are actually retrievable. Produced files are kept
in a temp folder printed at startup. Uploads are capped at 512 MB. Multipart
parsing uses `email.parser` from the standard library, so it keeps working on
Python 3.13+ where `cgi` was removed.

## Carrier

PNG is the recommended carrier. The implementation stores a self-describing
payload after the PNG stream, preserving the visible image bytes exactly. It is
not intended to survive image recompression or platforms that rewrite the file.
Embedding into an image that already carries a payload replaces the old payload
instead of stacking a second one.

## Security

The optional password mode uses PBKDF2-HMAC-SHA256-derived XOR keystream
encryption plus SHA-256 integrity checking. This is suitable as a local utility
but is not a substitute for a professionally audited cryptographic container.

## Version

`STEG --version` prints the version and build date. The web UI shows the same
stamp in its footer.
