#!/usr/bin/env bash
# Stegano Tool uninstaller - removes the launcher, keeps your files.
set -eu

removed=0
for dir in "${PREFIX:-/nonexistent}/bin" "$HOME/.local/bin"; do
  for name in STEG steg; do
    if [ -e "$dir/$name" ] || [ -L "$dir/$name" ]; then
      rm -f "$dir/$name" && echo "Removed $dir/$name" && removed=1
    fi
  done
done

if [ -e "$HOME/.config/fish/functions/STEG.fish" ]; then
  rm -f "$HOME/.config/fish/functions/STEG.fish" && echo "Removed fish function"
  removed=1
fi

if [ "$removed" -eq 0 ]; then
  echo "Nothing to remove - STEG was not installed in a known location."
fi
echo "Stegano Tool removed from PATH. The project folder is untouched."
