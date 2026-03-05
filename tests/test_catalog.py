import pytest
from conversations.catalog import _extract_metadata

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
