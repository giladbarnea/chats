#!/usr/bin/env python3
"""
Unit tests for tool filtering logic in Message.iter_visible_parts.
"""

import unittest

from conversations import ConversationFlags, Message
from conversations.parts import MessagePartKind


class TestToolFiltering(unittest.TestCase):
    def setUp(self):
        # Create a message with various tool calls
        self.tools = [
            {
                "type": "tool_use",
                "name": "Bash",
                "input": {"command": "ls -la"},
                "id": "toolu_01"
            },
            {
                "type": "tool_result", 
                "tool_use_id": "toolu_01",
                "content": "file1.txt file2.txt"
            },
            {
                "type": "tool_use",
                "name": "Read",
                "input": {"file_path": "file1.txt"},
                "id": "toolu_02"
            },
            {
                "type": "tool_result",
                "tool_use_id": "toolu_02", 
                "content": "some content"
            }
        ]
        self.message = Message(
            role="assistant",
            text="Here are some tools.",
            tools=self.tools
        )

    def test_show_tools_false(self):
        """Test that no tools are shown when show_tools is False."""
        flags = ConversationFlags(show_tools=False)
        parts = list(self.message.iter_visible_parts(flags))
        
        # Should only have text
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].kind, MessagePartKind.TEXT)

    def test_show_tools_true(self):
        """Test that all tools are shown when show_tools is True."""
        flags = ConversationFlags(show_tools=True)
        parts = list(self.message.iter_visible_parts(flags))
        
        # Text + 4 tool parts
        self.assertEqual(len(parts), 5)
        self.assertEqual(parts[0].kind, MessagePartKind.TEXT)
        self.assertTrue(all(p.kind == MessagePartKind.TOOL for p in parts[1:]))

    def test_filter_include_specific_tool(self):
        """Test including only a specific tool."""
        # Note: This relies on ConversationFlags accepting a string
        flags = ConversationFlags(show_tools="Bash")
        parts = list(self.message.iter_visible_parts(flags))
        
        # Text + 2 Bash parts (use and result)
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0].kind, MessagePartKind.TEXT)
        
        # Verify the tools are related to Bash
        # Part 1: Bash tool use
        self.assertEqual(parts[1].kind, MessagePartKind.TOOL)
        # Check name in attributes (list of tuples)
        # tool_to_parts returns ToolParts(tag, attrs=[(k,v)...], ...)
        # We expect attrs to contain ('name', 'Bash')
        attrs = dict(parts[1].data.attrs)
        self.assertEqual(attrs.get("name"), "Bash")
        
        # Part 2: Bash tool result
        self.assertEqual(parts[2].kind, MessagePartKind.TOOL)
        # tool_result doesn't have a name attribute by default, but we should ensure it's included.
        # Its tag should be 'tool-output'
        self.assertEqual(parts[2].data.tag, "tool-output")

    def test_filter_exclude_specific_tool(self):
        """Test excluding a specific tool."""
        flags = ConversationFlags(show_tools="!Read")
        parts = list(self.message.iter_visible_parts(flags))
        
        # Text + 2 Bash parts (Read is excluded)
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0].kind, MessagePartKind.TEXT)
        self.assertEqual(parts[1].data.attrs[0], ("name", "Bash"))


if __name__ == "__main__":
    unittest.main()
