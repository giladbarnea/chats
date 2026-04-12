import json
from pathlib import Path

import pytest
from conversations.catalog import _extract_metadata, _is_session_id

def test_extract_metadata():
    content = """---
session_id: 1234
directory: ~/my_dir
messages: 17
---
<some_xml>
"""
    meta = _extract_metadata(content)
    assert meta.get("session_id") == 1234
    assert meta.get("directory") == "~/my_dir"
    assert meta.get("messages") == 17

def test_extract_metadata_no_frontmatter():
    content = """<some_xml>
<tag></tag>
"""
    meta = _extract_metadata(content)
    assert meta == {}


class TestIsSessionId:
    """Test that _is_session_id accepts identifiers the shared resolver handles."""

    def test_standard_uuid(self):
        assert _is_session_id("5078a7c7-0646-43cc-9412-7e1454a282b4") is True

    def test_codex_ulid_style_id(self):
        """Codex session IDs are longer ULIDs — catalog should accept them."""
        assert _is_session_id("01961abc-def0-7123-89ab-codexsession0001") is True

    def test_existing_file_path_rejected(self, tmp_path):
        """Existing file paths are handled by _is_file_path, not _is_session_id."""
        f = tmp_path / "session.jsonl"
        f.write_text("{}\n")
        assert _is_session_id(str(f)) is False

    def test_multi_word_phrase_rejected(self):
        """Multi-word phrases are search text, not session IDs."""
        assert _is_session_id("fix the auth bug") is False

    def test_single_word_session_stem(self):
        """Single-word identifiers like file stems should be accepted."""
        assert _is_session_id("rollout-2026-04-10T09-15-00-01961abc") is True
