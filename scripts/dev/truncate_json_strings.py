#!/usr/bin/env python3
"""
Truncate long string values in a JSON file or from stdin.

Reads JSON from a file or stdin and recursively processes it to middle-truncate
any string values longer than 200 characters with "..." placeholder.
"""

import json
import sys
from pathlib import Path
from typing import Any


def truncate_string(text: str, max_length: int = 200) -> str:
    """
    Middle-truncate a string if it exceeds max_length.

    Args:
        text: String to potentially truncate
        max_length: Maximum allowed length (default: 200)

    Returns:
        Original string if under max_length, otherwise middle-truncated version
    """
    if len(text) <= max_length:
        return text

    # Calculate lengths for start and end portions
    # Reserve 3 chars for "..."
    available = max_length - 3
    start_len = available // 2
    end_len = available - start_len

    return f"{text[:start_len]}...{text[-end_len:]}"


def process_value(value: Any) -> Any:
    """
    Recursively process a JSON value, truncating strings as needed.

    Args:
        value: Any JSON-compatible value (dict, list, str, int, float, bool, None)

    Returns:
        Processed value with truncated strings
    """
    if isinstance(value, dict):
        return {key: process_value(val) for key, val in value.items()}
    elif isinstance(value, list):
        return [process_value(item) for item in value]
    elif isinstance(value, str):
        return truncate_string(value)
    else:
        # int, float, bool, None - return as-is
        return value


def main():
    """Main entry point."""
    try:
        # Determine input source: file or stdin
        if len(sys.argv) > 1:
            # Read from file
            file_path = Path(sys.argv[1])

            if not file_path.exists():
                print(f"Error: File not found: {file_path}", file=sys.stderr)
                sys.exit(1)

            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            # Read from stdin
            if sys.stdin.isatty():
                print("Usage: truncate_json_strings.py [<json-file-path>]", file=sys.stderr)
                print("  Reads from file if provided, or from stdin if not", file=sys.stderr)
                sys.exit(1)

            data = json.load(sys.stdin)

        # Process the data recursively
        processed_data = process_value(data)

        # Output to stdout
        json.dump(processed_data, sys.stdout, indent=2, ensure_ascii=False)
        print()  # Add newline at end

    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
