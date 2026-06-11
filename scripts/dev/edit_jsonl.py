#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Edit one existing JSONL field in place, using the current value as the type contract.

This is for agent-session JSONL files that are too large to open directly. The
script reads the file line by line, parses only the selected 0-indexed line,
updates one existing field, and atomically replaces the file. If anything is
invalid, the source file is left unchanged.

Usage:
  edit_jsonl.py <jsonl_file> <0-index> <dotpath> <new_value>
  edit_jsonl.py <jsonl_file> del <0-index>

Delete mode:
  Delete removes the whole JSONL line at the selected 0-index. It does not parse
  that line first, so it can also remove malformed records.

    edit_jsonl.py session.jsonl del 11

  A bare command like edit_jsonl.py del 11 is intentionally not supported: the
  script will not guess which JSONL file to mutate.

Mental model:
  The current value at <dotpath> decides what <new_value> must be.
  You do not annotate types in the CLI. You only pass one shell argument.

Dotpaths:
  Supported:
    .type
    .attachment.exitCode
    .message.content
    .message.content[0]
    .message.content[0].input.file_path

  Not supported:
    message.content          # must start with '.'
    .message.content[]       # no append
    .message.content[*]      # no wildcards
    .message.content[0:2]    # no slices
    .missing.path            # fields must already exist

Scalars:
  Existing string fields accept any shell argument as the literal string.
    edit_jsonl.py session.jsonl 0 '.type' 'foo bar'
    edit_jsonl.py session.jsonl 0 '.type' oneword

  Existing int fields accept only integer text.
    edit_jsonl.py session.jsonl 3 '.attachment.exitCode' 1

  Existing bool fields accept only lowercase true or false.
    edit_jsonl.py session.jsonl 9 '.isSidechain' false

  Existing null fields accept only null. The script cannot infer a new type from
  an existing null.

Lists and objects:
  Existing list fields accept only a JSON array. The array contents are free:
  mixed types, nested arrays, nested objects, nulls, booleans, whatever valid
  JSON allows.

    edit_jsonl.py session.jsonl 11 '.message.content' '[42, "hello world"]'
    edit_jsonl.py session.jsonl 11 '.message.content' "[42, \\"hello world\\"]"

  Existing object fields accept only a JSON object. The object shape and nested
  contents are free.

    edit_jsonl.py session.jsonl 11 '.message.content[0]' '{"i can":"set here","whatever":["i","want"],"life":{"is":"good","verified":true,"pain":[null]}}'

Invalid by design:
  These are type-contract violations and fail before replacing the file:

    edit_jsonl.py session.jsonl 11 '.message.content' 42
    edit_jsonl.py session.jsonl 11 '.message.content[0]' '[42]'
    edit_jsonl.py session.jsonl 11 '.type' '{"some":"object"}'

Shell quoting rule:
  Think only about the shell. Quotes used to keep spaces together are not type
  hints. If the existing field is numeric, both 1 and "1" reach the script as
  the same value. If the existing field is a string, explicit quote characters
  inside the argument are preserved literally.

Output shape:
  In set mode, the edited JSONL line is rewritten as compact JSON. Other lines
  are copied as they were. In delete mode, the selected line is omitted and all
  other lines are copied as they were.
"""
import argparse
import json
import math
import os
import pathlib
import re
import sys
import tempfile
from collections.abc import Callable


class JsonlEditError(Exception):
    """Raised for invalid edit requests; the source file is left unchanged."""


JSON_CONTAINER_FIELD_NAMES: dict[type[object], str] = {
    list: "list",
    dict: "object",
}
JSON_CONTAINER_SYNTAX_NAMES: dict[type[object], str] = {
    list: "array",
    dict: "object",
}


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
        f"field does not match object shape at {dotpath!r}: cannot access {token!r} on {json_type_name(container)}"
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
        f"field does not match object shape at {dotpath!r}: cannot set {token!r} on {json_type_name(container)}"
    )


def cast_value_to_existing_type(raw_value: str, existing_value: object) -> tuple[object, str | None]:
    """Cast a CLI value into the JSON type already present at the target.

    >>> cast_value_to_existing_type('42', 0)
    (42, None)
    >>> cast_value_to_existing_type('true', False)
    (True, None)
    >>> cast_value_to_existing_type('[42, "hello"]', [])
    ([42, 'hello'], None)
    >>> cast_value_to_existing_type('{"nested": [null]}', {})
    ({'nested': [None]}, None)
    """
    existing_type = type(existing_value)
    parsed_container = parse_json_container_when_present(raw_value)

    if parsed_container is not None:
        parsed_type, parsed_value = parsed_container
        if parsed_type is not existing_type:
            raise JsonlEditError(
                f"cannot set {json_type_name(existing_value)} field from "
                f"{JSON_CONTAINER_FIELD_NAMES[parsed_type]} value {raw_value!r}"
            )
        return parsed_value, None

    if existing_type in JSON_CONTAINER_FIELD_NAMES:
        field_name = JSON_CONTAINER_FIELD_NAMES[existing_type]
        syntax_name = JSON_CONTAINER_SYNTAX_NAMES[existing_type]
        raise JsonlEditError(f"cannot set {field_name} field from {raw_value!r}; expected a JSON {syntax_name}")

    if existing_type not in SCALAR_CASTERS:
        raise JsonlEditError(f"target value is not a supported editable type: {json_type_name(existing_value)}")

    new_value = SCALAR_CASTERS[existing_type](raw_value)
    warning = quoted_string_warning(raw_value) if existing_type is str else None
    return new_value, warning


def parse_json_container_when_present(raw_value: str) -> tuple[type[object], object] | None:
    stripped_value = raw_value.strip()
    if not stripped_value.startswith(("[", "{")):
        return None

    try:
        value = json.loads(stripped_value, parse_constant=reject_json_constant)
    except json.JSONDecodeError:
        return None

    value_type = type(value)
    if value_type not in JSON_CONTAINER_FIELD_NAMES:
        return None

    return value_type, value


def reject_json_constant(constant: str) -> object:
    raise JsonlEditError(f"invalid JSON constant in JSON value: {constant}")


def cast_string(raw_value: str) -> str:
    return raw_value


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


SCALAR_CASTERS: dict[type[object], Callable[[str], object]] = {
    str: cast_string,
    bool: cast_bool,
    int: cast_int,
    float: cast_float,
    type(None): cast_null,
}


def quoted_string_warning(raw_value: str) -> str | None:
    if len(raw_value) < 2 or not raw_value.startswith("'") or not raw_value.endswith("'"):
        return None

    return (
        f"{raw_value} was set with literal quotes. If you meant to just set a string, "
        "rerun without wrapping in quotes; the script sets values in the same types as "
        "the original field's value automatically."
    )


def json_type_name(value: object) -> str:
    if type(value) is str:
        return "string"

    if type(value) is bool:
        return "bool"

    if type(value) is int:
        return "int"

    if type(value) is float:
        return "float"

    if type(value) is list:
        return "list"

    if type(value) is dict:
        return "object"

    if value is None:
        return "null"

    return type(value).__name__


def replace_value(record: object, dotpath: str, raw_value: str) -> tuple[object, object, str | None]:
    """Replace one existing scalar, list, or object field in a parsed JSON record.

    >>> record = {'attachment': {'exitCode': 0}}
    >>> replace_value(record, '.attachment.exitCode', '1')[:2]
    (0, 1)
    >>> record
    {'attachment': {'exitCode': 1}}
    >>> record = {'message': {'content': [{'type': 'tool_use'}]}}
    >>> replace_value(record, '.message.content', '[42, "hello world"]')[:2]
    ([{'type': 'tool_use'}], [42, 'hello world'])
    >>> record = {'message': {'content': [{'old': True}]}}
    >>> replace_value(record, '.message.content[0]', '{"whatever": ["i", "want"]}')[:2]
    ({'old': True}, {'whatever': ['i', 'want']})
    """
    tokens = parse_dotpath(dotpath)
    parent = record

    for token in tokens[:-1]:
        parent = get_child(parent, token, dotpath)

    final_token = tokens[-1]
    existing_value = get_child(parent, final_token, dotpath)
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


def validate_edit_target(source_path: pathlib.Path, target_index: int) -> None:
    if target_index < 0:
        raise JsonlEditError(f"line index must be non-negative, got {target_index}")

    if not source_path.exists():
        raise JsonlEditError(f"file not found: {source_path}")

    if not source_path.is_file():
        raise JsonlEditError(f"not a file: {source_path}")


def edit_jsonl_file(
    source_path: pathlib.Path,
    target_index: int,
    dotpath: str,
    raw_value: str,
) -> tuple[object, object, str | None]:
    validate_edit_target(source_path, target_index)

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


def delete_jsonl_line(source_path: pathlib.Path, target_index: int) -> str:
    """Delete one physical JSONL line by 0-index and return the deleted line content.

    >>> import tempfile
    >>> with tempfile.NamedTemporaryFile('w+', encoding='utf-8') as file:
    ...     _ = file.write('{"a":1}\\n{"b":2}\\n')
    ...     file.flush()
    ...     deleted_line = delete_jsonl_line(pathlib.Path(file.name), 0)
    ...     deleted_line, pathlib.Path(file.name).read_text()
    ('{"a":1}', '{"b":2}\\n')
    """
    validate_edit_target(source_path, target_index)

    deleted_line: str | None = None
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
                    if current_index == target_index:
                        deleted_line, _line_ending = split_line_ending(line)
                        continue

                    temporary_file.write(line)

        if deleted_line is None:
            raise JsonlEditError(f"line index {target_index} does not exist")

        temporary_path.chmod(source_mode)
        os.replace(temporary_path, source_path)
        temporary_path = None
        return deleted_line

    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


class DocumentationArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        self.print_help(sys.stderr)
        self.exit(2, f"\nerror: {message}\n")


def parse_args() -> argparse.Namespace:
    parser = DocumentationArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=(
            "edit_jsonl.py <jsonl_file> <0-index> <dotpath> <new_value>\n"
            "       edit_jsonl.py <jsonl_file> del <0-index>"
        ),
    )
    parser.add_argument("arguments", nargs="*", metavar="args")
    parsed_args = parser.parse_args()
    arguments: list[str] = parsed_args.arguments

    if len(arguments) == 2 and arguments[0] == "del":
        parser.error("delete mode needs a JSONL file: edit_jsonl.py <jsonl_file> del <0-index>")

    if len(arguments) == 3 and arguments[1] == "del":
        return argparse.Namespace(
            command="delete",
            jsonl_file=arguments[0],
            index=parse_cli_index(arguments[2], parser),
        )

    if len(arguments) == 4 and arguments[1] != "del":
        return argparse.Namespace(
            command="set",
            jsonl_file=arguments[0],
            index=parse_cli_index(arguments[1], parser),
            dotpath=arguments[2],
            new_value=arguments[3],
        )

    parser.error("expected set mode '<jsonl_file> <0-index> <dotpath> <new_value>' or delete mode '<jsonl_file> del <0-index>'")


def parse_cli_index(raw_index: str, parser: argparse.ArgumentParser) -> int:
    try:
        return int(raw_index)
    except ValueError:
        parser.error(f"line index must be an integer, got {raw_index!r}")

    raise AssertionError("unreachable")


def display_value(value: object, limit: int = 80) -> str:
    rendered = repr(value)
    if len(rendered) <= limit:
        return rendered

    return rendered[: limit - 1] + "…"


def main() -> None:
    args = parse_args()
    source_path = pathlib.Path(args.jsonl_file).expanduser()

    try:
        if args.command == "delete":
            deleted_line = delete_jsonl_line(source_path, args.index)
            print(f"deleted {source_path}: index {args.index} {display_value(deleted_line)}")
            return

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
