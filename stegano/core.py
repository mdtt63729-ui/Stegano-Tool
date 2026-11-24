#!/usr/bin/env python3
"""
Stegano Tool core.

Lossless carrier: PNG. The payload is appended after a normal PNG stream with a
self-describing footer. The visible image bytes are kept exactly, and arbitrary
binary files can be recovered byte for byte.

Everything works on bytes, so the same code serves files, stdin, stdout and the
web UI. The path based helpers at the bottom are thin wrappers kept for
compatibility.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import struct
from pathlib import Path

MAGIC = b"STEGANO1"
FOOTER = struct.Struct(">8sQ32s")
SALT_LEN = 16
NONCE_LEN = 16
PBKDF2_ITERATIONS = 200_000
PNG_SIG = b"\x89PNG\r\n\x1a\n"
RECORD_VERSION = 1


# --------------------------------------------------------------------------- #
# crypto helpers
# --------------------------------------------------------------------------- #
def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def _keystream(key: bytes, n: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < n:
        out.extend(hashlib.sha256(key + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(out[:n])


def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS, dklen=32
    )


def _crypt(data: bytes, password: str, salt: bytes, nonce: bytes) -> bytes:
    key = _derive(password, salt)
    return bytes(a ^ b for a, b in zip(data, _keystream(key + nonce, len(data))))


# --------------------------------------------------------------------------- #
# byte level API
# --------------------------------------------------------------------------- #
def check_png(data: bytes) -> None:
    """Raise ValueError unless the buffer is a PNG image."""
    if not data.startswith(PNG_SIG):
        raise ValueError("Carrier must be a PNG image for lossless embedding.")


def read_record(image: bytes) -> dict:
    """Return the embedded record dict, verifying the footer and integrity."""
    if len(image) < FOOTER.size or image[-FOOTER.size:-FOOTER.size + 8] != MAGIC:
        raise ValueError("No Stegano Tool payload found.")
    magic, length, digest = FOOTER.unpack(image[-FOOTER.size:])
    start = len(image) - FOOTER.size - length
    if start < len(PNG_SIG):
        raise ValueError("Invalid embedded data.")
    blob = image[start:start + length]
    if _digest(blob) != digest:
        raise ValueError("Embedded data integrity check failed.")
    try:
        record = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Embedded data is not a valid Stegano record.") from exc
    if not isinstance(record, dict) or "payload" not in record:
        raise ValueError("Embedded data is not a valid Stegano record.")
    return record


def pack(image: bytes, payload: bytes, name: str, password: str | None = None) -> bytes:
    """Return a new PNG byte string with `payload` embedded."""
    check_png(image)
    image = strip(image) if has_payload(image) else image

    salt = secrets.token_bytes(SALT_LEN)
    nonce = secrets.token_bytes(NONCE_LEN)
    body = _crypt(payload, password, salt, nonce) if password else payload

    record = {
        "version": RECORD_VERSION,
        "name": Path(name or "payload.bin").name,
        "size": len(payload),
        "encrypted": bool(password),
        "salt": salt.hex(),
        "nonce": nonce.hex(),
        "sha256": _digest(payload).hex(),
        "payload": body.hex(),
    }
    blob = json.dumps(record, separators=(",", ":")).encode("utf-8")
    footer = FOOTER.pack(MAGIC, len(blob), _digest(blob))
    return image + blob + footer


def unpack(image: bytes, password: str | None = None) -> tuple[dict, bytes]:
    """Return (record, payload bytes) from a stegano PNG."""
    record = read_record(image)
    try:
        body = bytes.fromhex(record["payload"])
    except (TypeError, ValueError) as exc:
        raise ValueError("Embedded payload is corrupted.") from exc

    if record.get("encrypted"):
        if not password:
            raise ValueError("This payload is password protected.")
        try:
            salt = bytes.fromhex(record["salt"])
            nonce = bytes.fromhex(record["nonce"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Embedded payload is corrupted.") from exc
        body = _crypt(body, password, salt, nonce)

    if _digest(body).hex() != record.get("sha256"):
        raise ValueError("Wrong password or corrupted payload.")
    return record, body


def has_payload(image: bytes) -> bool:
    try:
        read_record(image)
        return True
    except ValueError:
        return False


def describe(image: bytes) -> dict:
    """Metadata of the embedded record, without the payload itself."""
    record = read_record(image)
    return {
        k: v for k, v in record.items() if k not in ("payload", "salt", "nonce")
    }


def strip(image: bytes) -> bytes:
    """Return the PNG bytes with any Stegano payload removed."""
    record = read_record(image)
    _, length, _ = FOOTER.unpack(image[-FOOTER.size:])
    start = len(image) - FOOTER.size - length
    if start < len(PNG_SIG):
        raise ValueError("Invalid embedded data.")
    del record
    return image[:start]


# --------------------------------------------------------------------------- #
# path based compatibility wrappers
# --------------------------------------------------------------------------- #
def hide(image_path, payload_path, output_path=None, password=None):
    image_p = Path(image_path)
    payload_p = Path(payload_path)
    data = pack(image_p.read_bytes(), payload_p.read_bytes(), payload_p.name, password)
    out = Path(output_path) if output_path else image_p.with_name(image_p.stem + "_steg.png")
    out.write_bytes(data)
    return out, {"name": payload_p.name, "size": payload_p.stat().st_size}


def inspect(image_path):
    return describe(Path(image_path).read_bytes())


def extract(image_path, output_dir=None, password=None):
    record, payload = unpack(Path(image_path).read_bytes(), password)
    outdir = Path(output_dir) if output_dir else Path(image_path).parent
    outdir.mkdir(parents=True, exist_ok=True)
    out = outdir / Path(record.get("name") or "payload.bin").name
    out.write_bytes(payload)
    return out


def remove(image_path, output_path=None):
    p = Path(image_path)
    data = strip(p.read_bytes())
    out = Path(output_path) if output_path else p.with_name(p.stem + "_clean.png")
    out.write_bytes(data)
    return out
