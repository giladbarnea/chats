from unittest.mock import patch

from conversations.catalog import _extract_metadata, _is_session_id, catalog_sessions


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


class TestCatalogSessionsGreppable:
    """Test that catalog_sessions only catalogs the FIRST session ID found in greppable input."""

    def test_finds_only_first_session_id_in_piped_content(self, tmp_path):
        """When piped content contains multiple session_id lines, only the first is cataloged."""
        piped = (
            "---\n"
            "session_id: 11111111-1111-1111-1111-111111111111\n"
            "directory: ~/dir1\n"
            "messages: 5\n"
            "---\n"
            "<content1/>\n"
            "\n"
            "---\n"
            "session_id: 22222222-2222-2222-2222-222222222222\n"
            "directory: ~/dir2\n"
            "messages: 10\n"
            "---\n"
            "<content2/>"
        )
        collected_ids: list[str] = []

        import conversations.catalog

        def fake_get_session_content(sid: str):
            nonlocal collected_ids
            collected_ids.append(sid)
            # Return content matching the first session
            return (
                "---\n"
                "session_id: 11111111-1111-1111-1111-111111111111\n"
                "directory: ~/dir1\n"
                "messages: 5\n"
                "---\n"
                "<content1/>"
            )

        with (
            patch.object(
                conversations.catalog,
                "_get_session_content",
                side_effect=fake_get_session_content,
            ),
            patch("conversations.catalog.subprocess.run"),
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit"),
        ):
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = piped
            catalog_sessions([])

        # Only the first session_id should have been processed
        assert collected_ids == ["11111111-1111-1111-1111-111111111111"]

    def test_finds_only_first_session_id_in_args(self, tmp_path):
        """When multiple session IDs are provided as arguments, only the first is cataloged."""
        collected_ids: list[str] = []

        import conversations.catalog

        def fake_get_session_content(sid: str):
            nonlocal collected_ids
            collected_ids.append(sid)
            return "---\nsession_id: " + sid + "\n---\n<content/>"

        with (
            patch.object(
                conversations.catalog,
                "_get_session_content",
                side_effect=fake_get_session_content,
            ),
            patch("conversations.catalog.subprocess.run"),
            patch("sys.stdin") as mock_stdin,
            patch("sys.exit"),
        ):
            mock_stdin.isatty.return_value = True
            catalog_sessions(["id1", "id2"])

        assert collected_ids == ["id1"]


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
