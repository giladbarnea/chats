"""Date-filter strings spanning the accepted shapes and the near-misses."""
import json, sys
cases = [
    None, "", "  ", "2024-12-15", "24-12-15", "2024-12-15T14:30", "2024-12-15 14:30",
    "2024-12-15T14:30:45", "24-12-15T14:30:45", "1h", "2d", "3w", "4m", "5y",
    "1H", "2D", "3W", "4M", "5Y", "0d", "999d", "1x", "d1", "1dd", "-1d",
    "bogus-date", "2024-13-01", "2024-02-30", "2024-12-15T25:00", "2024/12/15",
    "  2024-12-15  ", "2024-12-15T14", "15-12-2024", "20241215", "1.5d", "+1d",
]
json.dump(cases, open(sys.argv[1], "w"))
print(len(cases), "date cases")
