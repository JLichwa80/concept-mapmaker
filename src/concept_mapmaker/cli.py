"""Command-line interface for concept-mapmaker."""

import argparse

from . import __version__, builder, server


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="concept-map",
        description="Build and preview interactive concept maps from Markdown.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)

    build = commands.add_parser("build", help="build an HTML map and its PDF document")
    build.add_argument("input", help="source Markdown document")
    build.add_argument("--spec", help="YAML presentation spec "
                                      "(defaults to config.yaml beside the doc)")
    build.add_argument("--output", help="output HTML path (default: web/<stem>.html)")

    serve = commands.add_parser("serve", help="preview generated maps locally")
    serve.add_argument("map", nargs="?", help="HTML map path or filename under web/")
    serve.add_argument("--port", type=int, default=8080, help="port (default: 8080; 0 selects one)")
    serve.add_argument("--no-browser", action="store_true", help="do not open a browser")

    init = commands.add_parser("init", help="scaffold a starter map.md + config.yaml + map.css")
    init.add_argument("dir", nargs="?", default=".", help="target folder (default: current)")

    args = parser.parse_args(argv)
    if args.command == "build":
        return builder.run_build(args.input, spec=args.spec, output=args.output)
    if args.command == "init":
        return builder.run_init(args.dir)
    return server.serve(args.map, port=args.port, no_browser=args.no_browser)
