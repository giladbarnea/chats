"""Faithful reconstruction of the pre-rewrite `ch parse` argparse router.

Extracted verbatim from ac6599cc:src/chats/cli.py main() parse branch.
Conversion is stubbed: we only care about argparse routing behavior
(help text, usage errors, exit codes, stderr bytes).
"""

from __future__ import annotations

import argparse
import sys


def cmd_parse_json(input_file, *, output_format="xml"):
    raise SystemExit(f"CONVERTED input_file={input_file!r} format={output_format!r}")


def old_main(argv=None):
    if len(sys.argv) > 1 and sys.argv[1] == "parse":
        parser = argparse.ArgumentParser(
            prog="ch parse",
            description="Convert between structured ch JSON and XML-tagged Markdown",
        )
        parser.add_argument(
            "input_file",
            type=None,
            nargs="?",
            help="Input file (reads stdin when omitted)",
        )
        parser.add_argument(
            "-f",
            "--format",
            choices=["xml", "json"],
            default="xml",
            help="Output format: xml or json (default: xml)",
        )
        args = parser.parse_args(sys.argv[2:])
        cmd_parse_json(args.input_file, output_format=args.format)


if __name__ == "__main__":
    old_main()
