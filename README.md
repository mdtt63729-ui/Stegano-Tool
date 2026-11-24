# Stegano Tool — Aether OS

A local/offline Termux CLI + localhost Material-style web UI for lossless PNG payload storage.

## Install

```bash
git clone <YOUR-GITHUB-REPO>
cd stegano-tool
chmod +x install.sh
./install.sh
source ~/.bashrc
STEG
```

## CLI

Use ↑/↓ and Enter. The app can hide, extract, inspect, remove embedded data, and launch the local web UI.

## Web UI

Select **Start Web UI**. The app starts `127.0.0.1:8080` and attempts to open the Android browser automatically.

## Carrier

PNG is the recommended carrier. The implementation stores a self-describing payload after the PNG stream, preserving the visible image bytes exactly. It is not intended to survive image recompression or platforms that rewrite the file.

## Security

The optional password mode uses PBKDF2-HMAC-SHA256-derived XOR keystream encryption plus SHA-256 integrity checking. This is suitable as a local utility but is not a substitute for a professionally audited cryptographic container.
