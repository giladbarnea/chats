#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.13"
# dependencies = ["pyyaml"]
# ///

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_DIR = REPO_ROOT / "tests" / "data" / "murmur"
RAW_DIR = DATASET_DIR / "raw"
LABELS_PATH = DATASET_DIR / "labels.yaml"
DATASET_PATH = DATASET_DIR / "dataset.jsonl"
EXPORT_COMMAND = ["--only-assistant", "-f", "json"]


@dataclass(frozen=True)
class MurmurLabel:
    text: str
    difficulty: str = "standard"
    note: str | None = None


@dataclass(frozen=True)
class SessionLabels:
    session_id: str
    murmurs: tuple[MurmurLabel, ...]


def load_labels(labels_path: Path = LABELS_PATH) -> tuple[SessionLabels, ...]:
    """Load curated murmur labels from YAML.

    >>> labels = load_labels(LABELS_PATH)
    >>> any(session.session_id == "2cb581a8-658d-4040-bba2-8eef6a9c25e7" for session in labels)
    True
    """
    raw_labels = yaml.safe_load(labels_path.read_text(encoding="utf-8"))
    if not isinstance(raw_labels, dict):
        raise ValueError(f"Expected top-level dict in {labels_path}. Got: {type(raw_labels)!r}")

    sessions_raw = raw_labels.get("sessions")
    if not isinstance(sessions_raw, dict):
        raise ValueError(f"Expected 'sessions' mapping in {labels_path}. Got: {sessions_raw!r}")

    sessions: list[SessionLabels] = []
    for session_id, session_payload in sessions_raw.items():
        if not isinstance(session_id, str):
            raise ValueError(f"Expected session id str. Got: {session_id!r}")
        if not isinstance(session_payload, dict):
            raise ValueError(f"Expected mapping for {session_id}. Got: {session_payload!r}")

        murmurs_raw = session_payload.get("murmurs", [])
        if not isinstance(murmurs_raw, list):
            raise ValueError(f"Expected murmurs list for {session_id}. Got: {murmurs_raw!r}")

        murmurs: list[MurmurLabel] = []
        for murmur_raw in murmurs_raw:
            if not isinstance(murmur_raw, dict):
                raise ValueError(f"Expected murmur mapping for {session_id}. Got: {murmur_raw!r}")
            text = murmur_raw.get("text")
            if not isinstance(text, str):
                raise ValueError(f"Expected murmur text str for {session_id}. Got: {text!r}")
            difficulty = murmur_raw.get("difficulty", "standard")
            if difficulty not in {"standard", "tricky"}:
                raise ValueError(
                    f"Expected difficulty standard|tricky for {session_id}. Got: {difficulty!r}"
                )
            note = murmur_raw.get("note")
            if note is not None and not isinstance(note, str):
                raise ValueError(f"Expected note str|None for {session_id}. Got: {note!r}")
            murmurs.append(MurmurLabel(text=text, difficulty=difficulty, note=note))

        sessions.append(SessionLabels(session_id=session_id, murmurs=tuple(murmurs)))

    return tuple(sessions)


def export_session(session_id: str, output_path: Path) -> None:
    """Persist the assistant-only JSON export for one curated session."""
    completed = subprocess.run(
        ["ccc", session_id, *EXPORT_COMMAND],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(completed.stdout, encoding="utf-8")


def export_sessions(labels: tuple[SessionLabels, ...]) -> None:
    """Refresh all raw assistant-message exports from ccc."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for session in labels:
        export_session(session.session_id, RAW_DIR / f"{session.session_id}.json")


def extract_message_text(message: object) -> str:
    """Join visible string content from one exported assistant message.

    >>> extract_message_text({"content": ["Done."]})
    'Done.'
    """
    if not isinstance(message, dict):
        raise ValueError(f"Expected message dict. Got: {message!r}")

    content = message.get("content")
    if not isinstance(content, list):
        raise ValueError(f"Expected content list. Got: {content!r}")

    strings = [item for item in content if isinstance(item, str)]
    if not strings:
        raise ValueError(f"Expected at least one visible string in message. Got: {message!r}")

    return "\n\n".join(strings)


def build_dataset_rows(labels: tuple[SessionLabels, ...]) -> list[dict[str, object]]:
    """Flatten the curated sessions into a stable JSONL dataset."""
    rows: list[dict[str, object]] = []

    for session in labels:
        export_path = RAW_DIR / f"{session.session_id}.json"
        messages = json.loads(export_path.read_text(encoding="utf-8"))
        if not isinstance(messages, list):
            raise ValueError(f"Expected message list in {export_path}. Got: {type(messages)!r}")

        murmur_lookup = {label.text: label for label in session.murmurs}
        seen_murmur_texts: set[str] = set()

        for message in messages:
            text = extract_message_text(message)
            label = murmur_lookup.get(text)
            if label is not None:
                seen_murmur_texts.add(text)

            if not isinstance(message, dict):
                raise ValueError(f"Expected message dict in {export_path}. Got: {message!r}")

            original_index = message.get("original_index")
            if not isinstance(original_index, int):
                raise ValueError(
                    f"Expected original_index int in {export_path}. Got: {original_index!r}"
                )

            model = message.get("model")
            if model is not None and not isinstance(model, str):
                raise ValueError(f"Expected model str|None in {export_path}. Got: {model!r}")

            rows.append(
                {
                    "example_id": f"{session.session_id}:{original_index}",
                    "session_id": session.session_id,
                    "original_index": original_index,
                    "model": model,
                    "text": text,
                    "is_murmur": label is not None,
                    "difficulty": label.difficulty if label is not None else "standard",
                }
            )

        missing_texts = sorted(set(murmur_lookup) - seen_murmur_texts)
        if missing_texts:
            raise ValueError(
                f"Failed to find labeled murmur text(s) in {export_path}: {missing_texts!r}"
            )

    return rows


def write_dataset(rows: list[dict[str, object]], dataset_path: Path = DATASET_PATH) -> None:
    """Write one JSON object per assistant message.

    >>> path = Path('/tmp/murmur-dataset-doctest.jsonl')
    >>> write_dataset([{"example_id": "x", "text": "Done.", "is_murmur": True, "difficulty": "standard"}], path)
    >>> path.read_text(encoding='utf-8').strip()
    '{"example_id": "x", "text": "Done.", "is_murmur": true, "difficulty": "standard"}'
    >>> path.unlink()
    """
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    dataset_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    labels = load_labels()
    export_sessions(labels)
    rows = build_dataset_rows(labels)
    write_dataset(rows)
    print(f"Wrote {len(rows)} rows to {DATASET_PATH}")


if __name__ == "__main__":
    main()
