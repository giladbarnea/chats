#!/usr/bin/env bash
set -e

# Ensure shell tests are executable
chmod +x tests/test_basic.sh
chmod +x tests/test_flags.sh
chmod +x tests/test_colors.sh
chmod +x tests/test_format.sh
chmod +x tests/test_cli_seam.sh
chmod +x tests/test_name.sh
chmod +x tests/test_search_date.sh
chmod +x tests/test_raw_and_metadata.sh
chmod +x tests/test_rm.sh
chmod +x tests/test_tool_filter.sh
chmod +x tests/test_rich_whitespace.sh
chmod +x tests/test_search_only_id.sh
chmod +x tests/test_structured_rendering.sh

# Run Python unit tests first (fast, comprehensive)
echo "Running Python unit tests..."
uv run pytest tests/
echo ""

# Run shell tests (CLI seam verification)
./tests/test_basic.sh
./tests/test_cli_seam.sh
./tests/test_flags.sh
./tests/test_colors.sh
./tests/test_rich_whitespace.sh
./tests/test_tool_filter.sh
./tests/test_format.sh
./tests/test_raw_and_metadata.sh
./tests/test_name.sh
./tests/test_rm.sh
./tests/test_search_date.sh
./tests/test_search_only_id.sh
./tests/test_structured_rendering.sh

echo "\n🎉 All tests passed!"
