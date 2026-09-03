#!/usr/bin/env python3
"""Serve a built map (or the whole ``web/`` folder) over HTTP for local preview.

Opening a map via ``file://`` works for a single page but is fragile for deep links and any
cross-map navigation, so this serves over plain HTTP instead. Pass the map you want as a
positional argument; the server roots itself at that file's folder and opens it. With no
argument it serves ``web/`` under the caller's current project directory.

No dependencies -- Python stdlib only.

Usage:
    concept-map serve demo.html
    concept-map serve web/demo.html
    concept-map serve
    concept-map serve demo.html --port 8000
    concept-map serve demo.html --no-browser
"""

import functools
import http.server
import os
import socket
import socketserver
import sys
import threading
import webbrowser

def resolve_target(arg, project_root=None):
    """Return (serve_dir, open_path) for the optional map argument.

    No argument -> serve ``web/`` at the root, open nothing. Otherwise accept the map as an
    explicit path (``web/demo.html``) or as a bare name resolved inside ``web/``
    (``demo.html``); the server roots at the file's own folder so its same-folder links
    resolve. Exits with a clear message if the named file isn't found.
    """
    project_root = os.path.abspath(project_root or os.getcwd())
    web_dir = os.path.join(project_root, "web")
    if not arg:
        if not os.path.isdir(web_dir):
            sys.exit(f"Web directory not found: {web_dir}\nBuild a map first.")
        return web_dir, ""
    for cand in (arg, os.path.join(project_root, arg), os.path.join(web_dir, arg)):
        if os.path.isfile(cand):
            cand = os.path.abspath(cand)
            return os.path.dirname(cand), os.path.basename(cand)
    sys.exit(f"Map not found: {arg}\n"
             f"Looked from {project_root} and {web_dir}.\n"
             f"Build it first: concept-map build <document.md>")


def pick_port(preferred: int | None) -> int:
    """Return an available port. If *preferred* is given, require it (or fail)."""
    if preferred is not None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", preferred))
            except OSError:
                sys.exit(f"Port {preferred} is already in use. "
                         f"Pick another with --port or use --port 0 to auto-select.")
        return preferred
    # Auto-select: let the OS hand us a free port.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with terser, cache-disabled responses."""

    def end_headers(self):
        # Disable caching so a rebuild is always reflected on reload.
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("  %s - %s\n" % (self.address_string(), fmt % args))


def serve(map_arg=None, *, port=8080, no_browser=False, project_root=None) -> None:
    """Serve a built map (or the whole ``web/`` folder) over HTTP and open it.

    ``port`` 0 auto-selects a free port. Called by the ``concept-map serve`` CLI.
    """
    serve_dir, open_path = resolve_target(map_arg, project_root)
    port = pick_port(port or None)
    handler = functools.partial(QuietHandler, directory=serve_dir)

    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        base = f"http://127.0.0.1:{port}"
        print(f"Serving {serve_dir}")
        print(f"  {base}/{open_path}" if open_path else f"  {base}/")
        print("Press Ctrl+C to stop.")

        if not no_browser:
            url = f"{base}/{open_path}"
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")
