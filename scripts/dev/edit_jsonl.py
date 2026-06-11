#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Edit one scalar field in one JSONL record, without assuming any record schema."""
import argparse
import json
import math
import os
import pathlib
import re
import sys
import tempfile


class JsonlEditError(Exception):
    """Raised for invalid edit requests; the source file is left unchanged."""


def parse_dotpath(dotpath: str) -> list[str | int]:
    """Parse a small jq-like path subset: .key, .key.nested, and [index].

    >>> parse_dotpath('.attachment.exitCode')
    ['attachment', 'exitCode']
    >>> parse_dotpath('.message.content[0].text')
    ['message', 'content', 0, 'text']
    """
    if not dotpath.startswith(".") or dotpath == ".":
        raise JsonlEditError(f"dotpath must start with '.' and name a field: {dotpath!r}")

    tokens: list[str | int] = []
    index = 0

    while index < len(dotpath):
        character = dotpath[index]

        if character == ".":
            index = parse_key(dotpath, index, tokens)
            continue

        if character == "[":
            index = parse_list_index(dotpath, index, tokens)
            continue

        raise JsonlEditError(f"invalid dotpath syntax near {dotpath[index:]!r}")

    if not tokens:
        raise JsonlEditError(f"dotpath did not resolve to any field: {dotpath!r}")

    return tokens


def parse_key(dotpath: str, dot_index: int, tokens: list[str | int]) -> int:
    next_index = dot_index + 1

    if next_index >= len(dotpath):
        raise JsonlEditError(f"dotpath cannot end with '.': {dotpath!r}")

    if dotpath[next_index] == "[":
        return next_index

    key_start_index = next_index
    while next_index < len(dotpath) and dotpath[next_index] not in ".[":
        if dotpath[next_index] == "]":
            raise JsonlEditError(f"unexpected ']' in dotpath: {dotpath!r}")
        next_index += 1

    key = dotpath[key_start_index:next_index]
    if not key:
        raise JsonlEditError(f"empty field name in dotpath: {dotpath!r}")

    tokens.append(key)
    return next_index


def parse_list_index(dotpath: str, bracket_index: int, tokens: list[str | int]) -> int:
    end_index = dotpath.find("]", bracket_index)
    if end_index == -1:
        raise JsonlEditError(f"missing closing ']' in dotpath: {dotpath!r}")

    raw_index = dotpath[bracket_index + 1 : end_index]
    if not raw_index.isdecimal():
        raise JsonlEditError(f"list indexes must be non-negative integers: {dotpath!r}")

    tokens.append(int(raw_index))
    return end_index + 1


def is_scalar(value: object) -> bool:
    """Return True for JSON scalar values.

    >>> [is_scalar(value) for value in ['x', 1, 1.5, True, None, [], {}]]
    [True, True, True, True, True, False, False]
    """
    return value is None or type(value) in {str, int, float, bool}


def cast_value_to_existing_type(raw_value: str, existing_value: object) -> tuple[object, str | None]:
    """Cast a CLI string into the exact JSON scalar type already present at the target.

    >>> cast_value_to_existing_type('42', 0)
    (42, None)
    >>> cast_value_to_existing_type('true', False)
    (True, None)
    """
    if type(existing_value) is str:
        return raw_value, quoted_string_warning(raw_value)

    if type(existing_value) is bool:
        return cast_bool(raw_value), None

    if type(existing_value) is int:
        return cast_int(raw_value), None

    if type(existing_value) is float:
        return cast_float(raw_value), None

    if existing_value is None:
        return cast_null(raw_value), None

    raise JsonlEditError(f"target value is not a scalar: {type(existing_value).__name__}")


def quoted_string_warning(raw_value: str) -> str | None:
    if len(raw_value) < 2 or not raw_value.startswith("'") or not raw_value.endswith("'"):
        return None

    return (
        f"{raw_value} was set with literal quotes. If you meant to just set a string, "
        "rerun without wrapping in quotes; the script sets values in the same types as "
        "the original field's value automatically."
    )


def cast_bool(raw_value: str) -> bool:
    if raw_value == "true":
        return True

    if raw_value == "false":
        return False

    raise JsonlEditError(f"cannot set bool field from {raw_value!r}; expected true or false")


def cast_int(raw_value: str) -> int:
    if not re.fullmatch(r"[+-]?\d+", raw_value):
        raise JsonlEditError(f"cannot set int field from {raw_value!r}")

    return int(raw_value, 10)


def cast_float(raw_value: str) -> float:
    try:
        value = float(raw_value)
    except ValueError as error:
        raise JsonlEditError(f"cannot set float field from {raw_value!r}") from error

    if not math.isfinite(value):
        raise JsonlEditError(f"cannot set float field from non-finite value {raw_value!r}")

    return value


def cast_null(raw_value: str) -> None:
    if raw_value == "null":
        return None

    raise JsonlEditError(f"cannot infer a non-null type from existing null; expected 'null', got {raw_value!r}")


def get_child(container: object, token: str | int, dotpath: str) -> object:
    if type(container) is dict and type(token) is str:
        if token not in container:
            raise JsonlEditError(f"field does not exist at {dotpath!r}: missing key {token!r}")
        return container[token]

    if type(container) is list and type(token) is int:
        if token >= len(container):
            raise JsonlEditError(f"field does not exist at {dotpath!r}: list index {token} out of range")
        return container[token]

    raise JsonlEditError(
        f"field does not match object shape at {dotpath!r}: cannot access {token!r} on {type(container).__name__}"
    )


def set_child(container: object, token: str | int, value: object, dotpath: str) -> None:
    if type(container) is dict and type(token) is str:
        if token not in container:
            raise JsonlEditError(f"field does not exist at {dotpath!r}: missing key {token!r}")
        container[token] = value
        return

    if type(container) is list and type(token) is int:
        if token >= len(container):
            raise JsonlEditError(f"field does not exist at {dotpath!r}: list index {token} out of range")
        container[token] = value
        return

    raise JsonlEditError(
        f"field does not match object shape at {dotpath!r}: cannot set {token!r} on {type(container).__name__}"
    )


def replace_value(record: object, dotpath: str, raw_value: str) -> tuple[object, object, str | None]:
    """Replace one existing scalar field in a parsed JSON record.

    >>> record = {'attachment': {'exitCode': 0}}
    >>> replace_value(record, '.attachment.exitCode', '1')[:2]
    (0, 1)
    >>> record
    {'attachment': {'exitCode': 1}}
    """
    tokens = parse_dotpath(dotpath)
    parent = record

    for token in tokens[:-1]:
        parent = get_child(parent, token, dotpath)

    final_token = tokens[-1]
    existing_value = get_child(parent, final_token, dotpath)
    if not is_scalar(existing_value):
        raise JsonlEditError(f"target value at {dotpath!r} is {type(existing_value).__name__}, not a scalar")

    new_value, warning = cast_value_to_existing_type(raw_value, existing_value)
    set_child(parent, final_token, new_value, dotpath)
    return existing_value, new_value, warning


def split_line_ending(line: str) -> tuple[str, str]:
    if line.endswith("\r\n"):
        return line[:-2], "\r\n"

    if line.endswith("\n"):
        return line[:-1], "\n"

    return line, ""


def compact_json(record: object) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def edit_jsonl_file(source_path: pathlib.Path, target_index: int, dotpath: str, raw_value: str) -> tuple[object, object, str | None]:
    if target_index < 0:
        raise JsonlEditError(f"line index must be non-negative, got {target_index}")

    if not source_path.exists():
        raise JsonlEditError(f"file not found: {source_path}")

    if not source_path.is_file():
        raise JsonlEditError(f"not a file: {source_path}")

    old_value: object = None
    new_value: object = None
    warning: str | None = None
    updated = False
    temporary_path: pathlib.Path | None = None
    source_mode = source_path.stat().st_mode & 0o777

    try:
        with source_path.open("r", encoding="utf-8", newline="") as source_file:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="",
                dir=source_path.parent,
                prefix=f".{source_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as temporary_file:
                temporary_path = pathlib.Path(temporary_file.name)

                for current_index, line in enumerate(source_file):
                    if current_index != target_index:
                        temporary_file.write(line)
                        continue

                    content, line_ending = split_line_ending(line)
                    if not content.strip():
                        raise JsonlEditError(f"line index {target_index} is blank")

                    try:
                        record = json.loads(content)
                    except json.JSONDecodeError as error:
                        raise JsonlEditError(f"line index {target_index} is not valid JSON: {error}") from error

                    old_value, new_value, warning = replace_value(record, dotpath, raw_value)
                    temporary_file.write(compact_json(record) + line_ending)
                    updated = True

        if not updated:
            raise JsonlEditError(f"line index {target_index} does not exist")

        temporary_path.chmod(source_mode)
        os.replace(temporary_path, source_path)
        temporary_path = None
        return old_value, new_value, warning

    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Edit one existing scalar field in one 0-indexed JSONL record, preserving the field's JSON type."
    )
    parser.add_argument("jsonl_file", help="Path to the JSONL file to edit in place")
    parser.add_argument("index", type=int, help="0-indexed JSONL line to edit")
    parser.add_argument("dotpath", help="Simple jq-like dotpath, e.g. .type or .message.content[0].text")
    parser.add_argument("new_value", help="New scalar value, cast to the target field's existing JSON type")
    return parser.parse_args()


def display_value(value: object, limit: int = 80) -> str:
    rendered = repr(value)
    if len(rendered) <= limit:
        return rendered

    return rendered[: limit - 1] + "…"


def main() -> None:
    args = parse_args()
    source_path = pathlib.Path(args.jsonl_file).expanduser()

    try:
        old_value, new_value, warning = edit_jsonl_file(source_path, args.index, args.dotpath, args.new_value)
    except JsonlEditError as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)

    if warning:
        print(f"warning: {warning}", file=sys.stderr)

    print(
        f"updated {source_path}: index {args.index} {args.dotpath} "
        f"{display_value(old_value)} -> {display_value(new_value)}"
    )


if __name__ == "__main__":
    main()
