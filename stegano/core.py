#!/usr/bin/env python3
"""
Stegano Tool core.
Lossless carrier: PNG. The payload is appended after a normal PNG stream
with a self-describing footer. This keeps the visible image unchanged and
allows arbitrary binary files to be recovered exactly.
"""
from pathlib import Path
import hashlib, json, os, struct, secrets

MAGIC=b"STEGANO1"
FOOTER=struct.Struct(">8sQ32s")
HEADER_LEN=4
SALT_LEN=16
NONCE_LEN=16

def _digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def _keystream(key: bytes, n: int) -> bytes:
    out=bytearray()
    counter=0
    while len(out)<n:
        out.extend(hashlib.sha256(key+counter.to_bytes(8,"big")).digest())
        counter+=1
    return bytes(out[:n])

def _derive(password: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000, dklen=32)

def _crypt(data: bytes, password: str, salt: bytes, nonce: bytes) -> bytes:
    key=_derive(password, salt)
    return bytes(a^b for a,b in zip(data, _keystream(key+nonce, len(data))))

def _png_check(path: Path):
    sig=b"\x89PNG\r\n\x1a\n"
    with path.open("rb") as f:
        if f.read(8)!=sig:
            raise ValueError("Carrier must be a PNG image for lossless embedding.")

def hide(image_path, payload_path, output_path=None, password=None):
    image=Path(image_path); payload=Path(payload_path)
    _png_check(image)
    raw=payload.read_bytes()
    meta={"name":payload.name,"size":len(raw)}
    salt=secrets.token_bytes(SALT_LEN); nonce=secrets.token_bytes(NONCE_LEN)
    body=raw
    if password:
        body=_crypt(raw,password,salt,nonce)
    record={
        "version":1,
        "name":payload.name,
        "size":len(raw),
        "encrypted":bool(password),
        "salt":salt.hex(),
        "nonce":nonce.hex(),
        "sha256":_digest(raw).hex(),
        "payload":body.hex()
    }
    blob=json.dumps(record,separators=(",",":")).encode()
    footer=FOOTER.pack(MAGIC,len(blob),_digest(blob))
    out=Path(output_path) if output_path else image.with_name(image.stem+"_steg.png")
    out.write_bytes(image.read_bytes()+blob+footer)
    return out, meta

def _read_record(image_path):
    p=Path(image_path)
    data=p.read_bytes()
    if len(data)<FOOTER.size or data[-FOOTER.size:-FOOTER.size+8]!=MAGIC:
        raise ValueError("No Stegano Tool payload found.")
    magic,length,digest=FOOTER.unpack(data[-FOOTER.size:])
    start=len(data)-FOOTER.size-length
    if start<8:
        raise ValueError("Invalid embedded data.")
    blob=data[start:start+length]
    if _digest(blob)!=digest:
        raise ValueError("Embedded data integrity check failed.")
    return json.loads(blob.decode())

def inspect(image_path):
    r=_read_record(image_path)
    return {k:v for k,v in r.items() if k not in ("payload","salt","nonce")}

def extract(image_path, output_dir=None, password=None):
    r=_read_record(image_path)
    body=bytes.fromhex(r["payload"])
    if r["encrypted"]:
        if not password:
            raise ValueError("This payload is password protected.")
        body=_crypt(body,password,bytes.fromhex(r["salt"]),bytes.fromhex(r["nonce"]))
    if _digest(body).hex()!=r["sha256"]:
        raise ValueError("Wrong password or corrupted payload.")
    outdir=Path(output_dir or Path(image_path).parent)
    outdir.mkdir(parents=True,exist_ok=True)
    out=outdir/r["name"]
    out.write_bytes(body)
    return out

def remove(image_path, output_path=None):
    p=Path(image_path); data=p.read_bytes()
    r=_read_record(p)
    length=len(bytes.fromhex(r["payload"]))
    start=len(data)-FOOTER.size-len(json.dumps(r,separators=(",",":")).encode())
    # Reconstruct exact record length from footer.
    _,blob_len,_=_read_footer(data)
    start=len(data)-FOOTER.size-blob_len
    out=Path(output_path) if output_path else p.with_name(p.stem+"_clean.png")
    out.write_bytes(data[:start])
    return out

def _read_footer(data):
    return FOOTER.unpack(data[-FOOTER.size:])
