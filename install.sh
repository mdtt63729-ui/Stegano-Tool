#!/data/data/com.termux/files/usr/bin/bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/.local/bin"
mkdir -p "$BIN"
cat > "$BIN/STEG" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec python "$ROOT/stegano/cli.py" "\$@"
EOF
chmod +x "$BIN/STEG"
case ":$PATH:" in *":$BIN:"*) ;; *) echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc";; esac
echo
echo "Stegano Tool installed."
echo "Restart Termux or run: source ~/.bashrc"
echo "Then type: STEG"
