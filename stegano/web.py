#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, os, subprocess, urllib.parse, mimetypes, tempfile, webbrowser
from .core import hide, extract, inspect, remove

ROOT=Path(__file__).resolve().parent.parent
WEB=ROOT/"web"
HOST="127.0.0.1"; PORT=8080

class Handler(BaseHTTPRequestHandler):
    def _send(self, code=200, typ="text/html; charset=utf-8", body=b""):
        self.send_response(code); self.send_header("Content-Type",typ)
        self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path in ("/","/index.html"):
            self._send(body=(WEB/"index.html").read_bytes()); return
        self._send(404,body=b"Not found")
    def do_POST(self):
        # Browser sends multipart form data. Python stdlib's email parser handles it.
        import cgi
        env={"REQUEST_METHOD":"POST","CONTENT_TYPE":self.headers.get("Content-Type",""),
             "CONTENT_LENGTH":self.headers.get("Content-Length","0")}
        form=cgi.FieldStorage(fp=self.rfile,headers=self.headers,environ=env)
        try:
            action=form.getfirst("action","")
            img=form["image"] if "image" in form else None
            payload=form["payload"] if "payload" in form else None
            pw=form.getfirst("password","")
            work=Path(tempfile.mkdtemp(prefix="stegano-"))
            if img is not None and getattr(img,"file",None):
                imgp=work/(Path(img.filename).name or "image.png"); imgp.write_bytes(img.file.read())
            else: raise ValueError("Image is required.")
            if action=="hide":
                if payload is None or not getattr(payload,"file",None): raise ValueError("File is required.")
                pp=work/(Path(payload.filename).name or "payload.bin"); pp.write_bytes(payload.file.read())
                out=work/"stegano_output.png"; hide(imgp,pp,out,pw or None)
                self._send(200,"application/json",json.dumps({"ok":True,"file":out.name}).encode()); return
            if action=="inspect":
                self._send(200,"application/json",json.dumps({"ok":True,"data":inspect(imgp)}).encode()); return
            if action=="extract":
                out=extract(imgp,work,pw or None)
                self._send(200,"application/json",json.dumps({"ok":True,"file":out.name}).encode()); return
            if action=="remove":
                out=remove(imgp,work/"clean.png")
                self._send(200,"application/json",json.dumps({"ok":True,"file":out.name}).encode()); return
            raise ValueError("Unknown action.")
        except Exception as e:
            self._send(400,"application/json",json.dumps({"ok":False,"error":str(e)}).encode())

def serve():
    httpd=ThreadingHTTPServer((HOST,PORT),Handler)
    url=f"http://{HOST}:{PORT}"
    print(f"\nWeb UI: {url}\n")
    try:
        subprocess.Popen(["am","start","-a","android.intent.action.VIEW","-d",url],
                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except Exception:
        try: webbrowser.open(url)
        except Exception: pass
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: httpd.server_close()
