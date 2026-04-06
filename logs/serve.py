#!/usr/bin/env python3
"""Simple gallery server for dino quadruped renders."""
import http.server
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Dino Quadruped Renders</title>
<style>
body{background:#1a1a2e;color:#eee;font-family:sans-serif;padding:20px;text-align:center}
h1{color:#4ade80}
.grid{display:flex;flex-wrap:wrap;justify-content:center;gap:20px;margin-top:20px}
.card{background:#16213e;border-radius:12px;padding:15px;max-width:420px}
.card img{width:100%;border-radius:8px}
.card p{margin-top:8px;color:#94a3b8}
</style></head><body>
<h1>Dino Quadruped - PyBullet Renders</h1>
<p>12-DOF | SpotMicro ref | body 0.164m | stable standing & trot gait</p>
<div class="grid">
<div class="card"><img src="dino_front_perspective.png"><p>Front Perspective (Standing)</p></div>
<div class="card"><img src="dino_side_view.png"><p>Side View</p></div>
<div class="card"><img src="dino_top_down.png"><p>Top Down</p></div>
<div class="card"><img src="dino_trot_midstride.png"><p>Trot Gait Mid-Stride</p></div>
</div></body></html>"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        else:
            super().do_GET()
    def log_message(self, format, *args):
        pass

print("Gallery server at http://10.21.31.54:18888")
http.server.HTTPServer(("0.0.0.0", 18888), Handler).serve_forever()
