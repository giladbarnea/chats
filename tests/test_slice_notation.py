#!/usr/bin/env python3
"""
Unit tests for slice notation parsing.

Test matrix covers:
- Single indices: positive edge/interior, negative edge/interior, zero (error)
- Ranges: open-start, open-stop, closed, mixed bounds
- Error cases: zero in any position

Each test verifies both the parse_slice_notation output AND the actual
slicing behavior on a mock message list.
"""

import sys
from pathlib import Path
from typing import ClassVar

from chats import parse_slice_notation


class TestParseSliceNotation:
    """Test the parse_slice_notation function directly."""

    # --- Single Index Tests ---

    def test_single_positive_edge_first(self):
        """Case 1: '1' -> first message only (1-based index 1)"""
        start, stop = parse_slice_notation("1")
        assert (start, stop) == (0, 1), f"Expected (0, 1), got ({start}, {stop})"

    def test_single_positive_interior(self):
        """Case 2: '2' -> second message only"""
        start, stop = parse_slice_notation("2")
        assert (start, stop) == (1, 2), f"Expected (1, 2), got ({start}, {stop})"

    def test_single_negative_edge_last(self):
        """Case 3: '-1' -> last message only"""
        start, stop = parse_slice_notation("-1")
        assert (start, stop) == (-1, None), (
            f"Expected (-1, None), got ({start}, {stop})"
        )

    def test_single_negative_interior(self):
        """Case 4: '-2' -> second-to-last message only (THE BUG TEST)"""
        start, stop = parse_slice_notation("-2")
        # Must return (-2, -1) so messages[-2:-1] selects single element
        assert (start, stop) == (-2, -1), f"Expected (-2, -1), got ({start}, {stop})"

    def test_single_negative_interior_minus3(self):
        """Additional: '-3' -> third-to-last message only"""
        start, stop = parse_slice_notation("-3")
        assert (start, stop) == (-3, -2), f"Expected (-3, -2), got ({start}, {stop})"

    # --- Range with Open Stop (start:) ---

    def test_range_open_stop_positive(self):
        """Case 6: '2:' -> from second message to end"""
        start, stop = parse_slice_notation("2:")
        assert (start, stop) == (1, None), f"Expected (1, None), got ({start}, {stop})"

    def test_range_open_stop_negative(self):
        """Case 12: '-1:' -> last message to end (degenerate)"""
        start, stop = parse_slice_notation("-1:")
        assert (start, stop) == (-1, None), (
            f"Expected (-1, None), got ({start}, {stop})"
        )

    def test_range_open_stop_negative_interior(self):
        """'-2:' -> last 2 messages"""
        start, stop = parse_slice_notation("-2:")
        assert (start, stop) == (-2, None), (
            f"Expected (-2, None), got ({start}, {stop})"
        )

    # --- Range with Open Start (:stop) ---

    def test_range_open_start_positive(self):
        """Case 13: ':2' -> up to (not including) second message"""
        start, stop = parse_slice_notation(":2")
        # 1-based stop 2 -> 0-based stop 1
        assert (start, stop) == (None, 1), f"Expected (None, 1), got ({start}, {stop})"

    def test_range_open_start_negative_edge(self):
        """':-1' -> all except last message"""
        start, stop = parse_slice_notation(":-1")
        assert (start, stop) == (None, -1), (
            f"Expected (None, -1), got ({start}, {stop})"
        )

    def test_range_open_start_negative_interior(self):
        """Case 7: ':-2' -> all except last 2 messages"""
        start, stop = parse_slice_notation(":-2")
        assert (start, stop) == (None, -2), (
            f"Expected (None, -2), got ({start}, {stop})"
        )

    # --- Closed Ranges ---

    def test_range_closed_positive_positive(self):
        """Case 8: '2:4' -> messages 2 and 3 (1-based)"""
        start, stop = parse_slice_notation("2:4")
        # 1-based [2,4) -> 0-based [1,3)
        assert (start, stop) == (1, 3), f"Expected (1, 3), got ({start}, {stop})"

    def test_range_closed_negative_negative(self):
        """Case 9: '-3:-1' -> third-to-last and second-to-last"""
        start, stop = parse_slice_notation("-3:-1")
        assert (start, stop) == (-3, -1), f"Expected (-3, -1), got ({start}, {stop})"

    def test_range_mixed_positive_negative_edge(self):
        """Case 10: '2:-1' -> from second to (not including) last"""
        start, stop = parse_slice_notation("2:-1")
        assert (start, stop) == (1, -1), f"Expected (1, -1), got ({start}, {stop})"

    def test_range_mixed_positive_negative_interior(self):
        """Case 11: '2:-2' -> from second to (not including) second-to-last"""
        start, stop = parse_slice_notation("2:-2")
        assert (start, stop) == (1, -2), f"Expected (1, -2), got ({start}, {stop})"

    # --- No slice ---

    def test_none_returns_full_range(self):
        """None input -> (None, None) for full range"""
        start, stop = parse_slice_notation(None)
        assert (start, stop) == (None, None), (
            f"Expected (None, None), got ({start}, {stop})"
        )

    def test_empty_string_returns_full_range(self):
        """Empty string -> (None, None) for full range"""
        start, stop = parse_slice_notation("")
        assert (start, stop) == (None, None), (
            f"Expected (None, None), got ({start}, {stop})"
        )


class TestSliceBehavior:
    """Test that slice bounds produce correct message selection."""

    # Simulate a message list with indices 1-6 (6 messages)
    MESSAGES: ClassVar[list[str]] = ["msg1", "msg2", "msg3", "msg4", "msg5", "msg6"]

    def slice_messages(self, slice_str):
        """Helper: parse slice and apply to test messages."""
        start, stop = parse_slice_notation(slice_str)
        return self.MESSAGES[start:stop]

    # --- Single indices must return exactly 1 message ---

    def test_behavior_single_positive_first(self):
        """'1' selects first message only"""
        result = self.slice_messages("1")
        assert result == ["msg1"], f"Expected ['msg1'], got {result}"

    def test_behavior_single_positive_interior(self):
        """'3' selects third message only"""
        result = self.slice_messages("3")
        assert result == ["msg3"], f"Expected ['msg3'], got {result}"

    def test_behavior_single_negative_last(self):
        """'-1' selects last message only"""
        result = self.slice_messages("-1")
        assert result == ["msg6"], f"Expected ['msg6'], got {result}"

    def test_behavior_single_negative_interior(self):
        """'-2' selects second-to-last message only (THE BUG TEST)"""
        result = self.slice_messages("-2")
        assert result == ["msg5"], f"Expected ['msg5'], got {result}"
        assert len(result) == 1, (
            f"Single index must return exactly 1 message, got {len(result)}"
        )

    def test_behavior_single_negative_minus3(self):
        """'-3' selects third-to-last message only"""
        result = self.slice_messages("-3")
        assert result == ["msg4"], f"Expected ['msg4'], got {result}"
        assert len(result) == 1, (
            f"Single index must return exactly 1 message, got {len(result)}"
        )

    # --- Ranges ---

    def test_behavior_range_open_stop(self):
        """'3:' selects from third to end"""
        result = self.slice_messages("3:")
        assert result == ["msg3", "msg4", "msg5", "msg6"], f"Got {result}"

    def test_behavior_range_open_start(self):
        """':3' selects up to (not including) third"""
        result = self.slice_messages(":3")
        assert result == ["msg1", "msg2"], f"Got {result}"

    def test_behavior_range_closed(self):
        """'2:5' selects messages 2, 3, 4"""
        result = self.slice_messages("2:5")
        assert result == ["msg2", "msg3", "msg4"], f"Got {result}"

    def test_behavior_range_negative_stop(self):
        """':-2' selects all except last 2"""
        result = self.slice_messages(":-2")
        assert result == ["msg1", "msg2", "msg3", "msg4"], f"Got {result}"

    def test_behavior_range_negative_start(self):
        """'-3:' selects last 3"""
        result = self.slice_messages("-3:")
        assert result == ["msg4", "msg5", "msg6"], f"Got {result}"

    def test_behavior_range_mixed(self):
        """'2:-2' selects from second to (not including) second-to-last"""
        result = self.slice_messages("2:-2")
        assert result == ["msg2", "msg3", "msg4"], f"Got {result}"


class TestSliceErrorCases:
    """Test error handling for invalid slice notation."""

    def test_zero_index_exits(self):
        """Case 5: '0' should exit with error"""
        import subprocess

        result = subprocess.run(
            [
                "python3",
                "-c",
                "from chats import parse_slice_notation; parse_slice_notation('0')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, "Expected non-zero exit for index 0"
        assert "Index must be >= 1 or < 0" in result.stderr

    def test_zero_start_exits(self):
        """Case 14: '0:' should exit with error"""
        import subprocess

        result = subprocess.run(
            [
                "python3",
                "-c",
                "from chats import parse_slice_notation; parse_slice_notation('0:')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, "Expected non-zero exit for start index 0"
        assert "Start index must be >= 1 or < 0" in result.stderr

    def test_zero_stop_exits(self):
        """':0' should exit with error"""
        import subprocess

        result = subprocess.run(
            [
                "python3",
                "-c",
                "from chats import parse_slice_notation; parse_slice_notation(':0')",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode != 0, "Expected non-zero exit for stop index 0"
        assert "Stop index must be >= 1 or < 0" in result.stderr


if __name__ == "__main__":
    import subprocess

    # Run with pytest if available, otherwise basic execution
    result = subprocess.run(
        ["python3", "-m", "pytest", __file__, "-v", "--tb=short"],
        cwd=Path(__file__).parent.parent,
        check=False,
    )
    sys.exit(result.returncode)
