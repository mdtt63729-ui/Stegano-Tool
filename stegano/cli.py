#!/usr/bin/env python3
"""
Stegano Tool command line interface.

Two ways in, same engine:

  * subcommands  - scriptable, works in any shell and in pipes
  * interactive  - the arrow-key menu, when started with no arguments on a TTY

`-` means stdin (input) or stdout (output), so payloads can be piped:

  cat secret.zip | STEG hide photo.png - -o out.png
  STEG extract out.png -o - > secret.zip
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

# Allow `python3 stegano/cli.py` and `./stegano/cli.py` as well as
# `python3 -m stegano.cli`: give the module a package context when run as a file.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    __package__ = "stegano"

from . import BUILD, VERSION
from .core import (
    check_png,
    describe,
    has_payload,
    pack,
    strip,
    unpack,
)

STAMP = f"STEG {VERSION} (build {BUILD})"
PNG_DEFAULT = "stegano_output.png"


# --------------------------------------------------------------------------- #
# io helpers
# --------------------------------------------------------------------------- #
def read_bytes(path: str, label: str) -> bytes:
    if path == "-":
        return sys.stdin.buffer.read()
    p = Path(path).expanduser()
    if not p.exists():
        raise SystemExit(f"{label} not found: {path}")
    return p.read_bytes()


def write_bytes(path: str | None, data: bytes, default: str) -> str:
    """Write to a file, or to stdout when path is '-'. Returns a label."""
    if path == "-":
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        return "stdout"
    out = Path(path).expanduser() if path else Path(default)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return str(out)


def note(msg: str) -> None:
    """Human messages go to stderr so pipes stay clean."""
    print(msg, file=sys.stderr, flush=True)


def resolve_password(given: str | None, *, needed_hint: str = "") -> str | None:
    if given == "-":
        if sys.stdin.isatty():
            return getpass.getpass("Password: ") or None
        line = sys.stdin.readline().strip()
        return line or None
    if given is not None:
        return given or None
    env = os.environ.get("STEGANO_PASSWORD")
    if env:
        return env
    if needed_hint and sys.stdin.isatty():
        return getpass.getpass(needed_hint) or None
    return None


# --------------------------------------------------------------------------- #
# subcommands
# --------------------------------------------------------------------------- #
def cmd_hide(args) -> int:
    image = read_bytes(args.image, "Image")
    payload = read_bytes(args.payload, "Payload")
    name = args.name or ("payload.bin" if args.payload == "-" else Path(args.payload).name)
    password = resolve_password(args.password)

    out = write_bytes(args.output, pack(image, payload, name, password), PNG_DEFAULT)
    note(f"Created: {out}")
    note(f"Embedded: {name} ({len(payload)} bytes)")
    return 0


def cmd_extract(args) -> int:
    image = read_bytes(args.image, "Image")
    password = resolve_password(args.password, needed_hint="Password: ")
    record, payload = unpack(image, password)

    name = Path(record.get("name") or "payload.bin").name
    if args.output == "-":
        target = write_bytes("-", payload, name)
    elif args.output:
        target = write_bytes(args.output, payload, name)
    else:
        default = str(Path(args.image).expanduser().parent / name) if args.image != "-" else name
        target = write_bytes(None, payload, default)
    note(f"Extracted: {target} ({len(payload)} bytes)")
    return 0


def cmd_inspect(args) -> int:
    image = read_bytes(args.image, "Image")
    info = describe(image)
    if args.json:
        import json

        print(json.dumps(info, indent=2))
    else:
        for k, v in info.items():
            print(f"{k}: {v}")
    return 0


def cmd_remove(args) -> int:
    image = read_bytes(args.image, "Image")
    out = write_bytes(args.output, strip(image), "stegano_clean.png")
    note(f"Created: {out}")
    return 0


def cmd_web(args) -> int:
    from .web import serve

    serve(host=args.host, port=args.port, open_browser=not args.no_browser)
    return 0


def cmd_menu(args) -> int:
    return interactive()


# --------------------------------------------------------------------------- #
# interactive menu
# --------------------------------------------------------------------------- #
MENU_ITEMS = [
    "Hide File",
    "Extract File",
    "View Embedded Data",
    "Remove Embedded Data",
    "Start Web UI",
    "Settings",
    "Exit",
]


def ask(prompt: str, default: str = "") -> str:
    try:
        value = input(prompt).strip()
    except EOFError:
        raise SystemExit(0)
    return value or default


def pause() -> None:
    if sys.stdin.isatty():
        try:
            input("\nPress Enter...")
        except EOFError:
            pass


def select_arrow(items: list[str]) -> int:
    idx = 0
    while True:
        os.system("clear" if os.name != "nt" else "cls")
        print(f"\n  STEGANO TOOL  {VERSION}\n  by Aether OS\n")
        for i, item in enumerate(items):
            print(("  \033[97m> " + item + "\033[0m") if i == idx else "    " + item)
        print("\n  Up/Down navigate   Enter select   q quit")
        ch = sys.stdin.read(1)
        if ch == "":
            raise SystemExit(0)
        if ch == "\x1b":
            seq = sys.stdin.read(2)
            if seq == "[A":
                idx = (idx - 1) % len(items)
            elif seq == "[B":
                idx = (idx + 1) % len(items)
        elif ch in ("\n", "\r"):
            return idx
        elif ch in ("q", "Q", "\x03"):
            return len(items) - 1


def select_numbered(items: list[str]) -> int:
    """Fallback for pipes, dumb terminals and Windows consoles."""
    print(f"\n  STEGANO TOOL  {VERSION}\n  by Aether OS\n")
    for i, item in enumerate(items, 1):
        print(f"   {i}. {item}")
    raw = ask("\n  Choice (1-%d, q to quit): " % len(items))
    if raw.lower() == "q":
        return len(items) - 1
    if raw.isdigit() and 1 <= int(raw) <= len(items):
        return int(raw) - 1
    print("  Invalid choice.")
    return -2


def interactive() -> int:
    print(STAMP, file=sys.stderr)
    while True:
        if sys.stdin.isatty():
            choice = select_arrow(MENU_ITEMS)
        else:
            choice = select_numbered(MENU_ITEMS)
            if choice == -2:
                continue
        try:
            if choice == 0:
                image = ask("\nPNG image path: ")
                payload = ask("File to embed (- for stdin): ")
                password = ask("Password (blank = none): ")
                out = ask("Output PNG (blank = automatic, - for stdout): ") or None
                data = read_bytes(payload, "Payload")
                name = "payload.bin" if payload == "-" else Path(payload).name
                target = write_bytes(out, pack(read_bytes(image, "Image"), data, name, password or None), PNG_DEFAULT)
                print(f"\nCreated: {target}\nEmbedded: {name} ({len(data)} bytes)")
            elif choice == 1:
                image = ask("\nStegano PNG path: ")
                out = ask("Output file or dir (blank = image folder, - for stdout): ") or None
                password = resolve_password(ask("Password if protected: ") or None, needed_hint="Password: ")
                record, data = unpack(read_bytes(image, "Image"), password)
                name = Path(record.get("name") or "payload.bin").name
                if out and out != "-":
                    target = write_bytes(out, data, name)
                elif out == "-":
                    target = write_bytes("-", data, name)
                else:
                    base = Path(image).expanduser().parent if image != "-" else Path(".")
                    target = write_bytes(None, data, str(base / name))
                print(f"\nExtracted: {target}")
            elif choice == 2:
                image = ask("\nStegano PNG path: ")
                for k, v in describe(read_bytes(image, "Image")).items():
                    print(f"{k}: {v}")
            elif choice == 3:
                image = ask("\nStegano PNG path: ")
                out = ask("Clean output PNG (blank = automatic, - for stdout): ") or None
                print(f"\nCreated: {write_bytes(out, strip(read_bytes(image, 'Image')), 'stegano_clean.png')}")
            elif choice == 4:
                from .web import serve

                serve()
            elif choice == 5:
                print(f"\n{STAMP}\nPayload format: v1 footer after the PNG stream")
                print(f"PBKDF2-HMAC-SHA256 rounds: 200000")
                print("Settings are kept minimal for the offline-first build.")
            else:
                print("\nGoodbye.\n")
                return 0
        except (ValueError, SystemExit) as exc:
            if isinstance(exc, SystemExit):
                raise
            print(f"\nError: {exc}")
        except OSError as exc:
            print(f"\nError: {exc}")
        pause()


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="STEG",
        description="Stegano Tool - hide any file inside a PNG, losslessly.",
        epilog="With no arguments the interactive menu starts. Use - for stdin/stdout.",
    )
    p.add_argument("-V", "--version", action="version", version=STAMP)
    sub = p.add_subparsers(dest="command")

    h = sub.add_parser("hide", help="embed a file into a PNG")
    h.add_argument("image", help="carrier PNG")
    h.add_argument("payload", help="file to embed, or - for stdin")
    h.add_argument("-o", "--output", help="output PNG (default stegano_output.png), or - for stdout")
    h.add_argument("-p", "--password", help="encrypt with a password, or - to prompt/read stdin")
    h.add_argument("-n", "--name", help="filename to store inside the record")
    h.set_defaults(func=cmd_hide)

    e = sub.add_parser("extract", help="recover the embedded file")
    e.add_argument("image", help="stegano PNG, or - for stdin")
    e.add_argument("-o", "--output", help="output file or directory, or - for stdout")
    e.add_argument("-p", "--password", help="password, or - to prompt/read stdin")
    e.set_defaults(func=cmd_extract)

    i = sub.add_parser("inspect", help="show the embedded record")
    i.add_argument("image", help="stegano PNG, or - for stdin")
    i.add_argument("--json", action="store_true", help="print as JSON")
    i.set_defaults(func=cmd_inspect)

    r = sub.add_parser("remove", help="strip the embedded data")
    r.add_argument("image", help="stegano PNG, or - for stdin")
    r.add_argument("-o", "--output", help="clean PNG, or - for stdout")
    r.set_defaults(func=cmd_remove)

    w = sub.add_parser("web", help="start the local web UI")
    w.add_argument("--host", default="127.0.0.1", help="bind address (default 127.0.0.1)")
    w.add_argument("--port", type=int, default=8080, help="port (default 8080)")
    w.add_argument("--no-browser", action="store_true", help="do not open a browser")
    w.set_defaults(func=cmd_web)

    m = sub.add_parser("menu", help="start the interactive menu")
    m.set_defaults(func=cmd_menu)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        # No arguments: always start the menu. On a pipe or a dumb terminal the
        # numbered menu is used, so `STEG` works everywhere.
        return interactive()
    try:
        return args.func(args) or 0
    except ValueError as exc:
        note(f"Error: {exc}")
        return 1
    except OSError as exc:
        note(f"Error: {exc}")
        return 1
    except BrokenPipeError:
        try:
            sys.stdout.close()
        except Exception:
            pass
        return 0


if __name__ == "__main__":
    sys.exit(main())
