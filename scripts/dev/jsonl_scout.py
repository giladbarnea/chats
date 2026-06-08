#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = ["rich"]
# ///
"""Generic JSONL bloat scout. Zero assumptions about shape."""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from rich import box
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

console = Console()


def normalize(path: str) -> str:
    return re.sub(r"\[\d+\]", "[*]", path)


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f}KB"
    return f"{n}B"


def savings_at_cap(sizes: list[int], cap: int) -> int:
    return sum(max(0, s - cap) for s in sizes)


class Stats:
    def __init__(self) -> None:
        # String paths
        self.path_total: dict[str, int] = defaultdict(int)
        self.path_occ: dict[str, int] = defaultdict(int)
        self.path_max: dict[str, tuple[int, int]] = {}  # norm -> (size, lineno)
        self.path_presence: dict[str, set[int]] = defaultdict(set)
        self.path_sizes: dict[str, list[int]] = defaultdict(list)

        # Array paths
        self.array_lengths: dict[str, list[int]] = defaultdict(list)
        self.array_child_bytes: dict[str, int] = defaultdict(int)

        # Redundancy
        self.path_hashes: dict[str, Counter] = defaultdict(Counter)
        self.path_hash_bytes: dict[str, dict[bytes, int]] = defaultdict(lambda: defaultdict(int))

        # Per-line: (lineno, line_bytes, top_contributing_path, top_path_bytes)
        self.line_info: list[tuple[int, int, str, int]] = []

        self.file_bytes: int = 0
        self.total_lines: int = 0
        self.errors: int = 0

    def _visit(self, obj: object, prefix: str, lineno: int, line_path_bytes: dict[str, int]) -> int:
        """Recursively traverse obj, recording all string/array metrics. Returns string bytes consumed."""
        if isinstance(obj, str):
            norm = normalize(prefix)
            size = len(obj.encode())
            self.path_total[norm] += size
            self.path_occ[norm] += 1
            self.path_presence[norm].add(lineno)
            self.path_sizes[norm].append(size)
            line_path_bytes[norm] += size
            cur = self.path_max.get(norm)
            if cur is None or size > cur[0]:
                self.path_max[norm] = (size, lineno)
            h = hashlib.md5(obj.encode(), usedforsecurity=False).digest()
            self.path_hashes[norm][h] += 1
            self.path_hash_bytes[norm][h] += size
            return size

        if isinstance(obj, dict):
            total = 0
            for k, v in obj.items():
                total += self._visit(v, f"{prefix}.{k}", lineno, line_path_bytes)
            return total

        if isinstance(obj, list):
            norm = normalize(prefix)
            child_bytes = 0
            for i, item in enumerate(obj):
                child_bytes += self._visit(item, f"{prefix}[{i}]", lineno, line_path_bytes)
            self.array_lengths[norm].append(len(obj))
            self.array_child_bytes[norm] += child_bytes
            return child_bytes

        return 0

    def ingest(self, path: Path) -> None:
        self.file_bytes = path.stat().st_size
        for i, line in enumerate(path.read_text(errors="replace").splitlines()):
            if not line.strip():
                continue
            lineno = i + 1
            self.total_lines += 1
            line_bytes = len(line.encode())
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                self.errors += 1
                self.line_info.append((lineno, line_bytes, "<parse error>", 0))
                continue
            line_path_bytes: dict[str, int] = defaultdict(int)
            self._visit(obj, "", lineno, line_path_bytes)
            if line_path_bytes:
                top = max(line_path_bytes, key=lambda k: line_path_bytes[k])
                self.line_info.append((lineno, line_bytes, top, line_path_bytes[top]))
            else:
                self.line_info.append((lineno, line_bytes, "<none>", 0))


def render(stats: Stats, top_n: int, outlier_n: int) -> None:
    fb = stats.file_bytes

    # ── Overview ──────────────────────────────────────────────────────────────
    console.print(Rule("[bold cyan]JSONL Bloat Scout[/bold cyan]"))
    console.print(
        f"  [bold]{fmt(fb)}[/bold] ({fb:,} bytes)  ·  "
        f"[bold]{stats.total_lines}[/bold] lines  ·  "
        f"{stats.errors} parse errors\n"
    )

    # ── 1. String path heat ───────────────────────────────────────────────────
    console.print(Rule("[bold]1 · String paths by total bytes[/bold]"))
    t = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
    t.add_column("Path")
    t.add_column("Total", justify="right")
    t.add_column("% file", justify="right")
    t.add_column("Occ", justify="right")
    t.add_column("Avg", justify="right")
    t.add_column("Max (line)", justify="right")
    t.add_column("Presence", justify="right")

    for norm_path, total in sorted(stats.path_total.items(), key=lambda x: x[1], reverse=True)[:top_n]:
        occ = stats.path_occ[norm_path]
        max_size, max_line = stats.path_max.get(norm_path, (0, 0))
        presence = len(stats.path_presence[norm_path]) / stats.total_lines
        t.add_row(
            norm_path,
            fmt(total),
            f"{total / fb:.1%}",
            str(occ),
            fmt(total // occ),
            f"{fmt(max_size)} (L{max_line})",
            f"{presence:.0%}",
        )
    console.print(t)

    # ── 2. Array cardinality ──────────────────────────────────────────────────
    fat_arrays = {
        p: (lengths, stats.array_child_bytes[p])
        for p, lengths in stats.array_lengths.items()
        if stats.array_child_bytes[p] > fb * 0.005
    }
    if fat_arrays:
        console.print(Rule("[bold]2 · Array paths by child bytes[/bold]"))
        at = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
        at.add_column("Array path")
        at.add_column("Child bytes", justify="right")
        at.add_column("% file", justify="right")
        at.add_column("Max len", justify="right")
        at.add_column("Avg len", justify="right")
        at.add_column("Total items", justify="right")
        at.add_column("Avg bytes/item", justify="right")

        for norm_path, (lengths, child_bytes) in sorted(fat_arrays.items(), key=lambda x: x[1][1], reverse=True)[:top_n]:
            total_items = sum(lengths)
            at.add_row(
                norm_path,
                fmt(child_bytes),
                f"{child_bytes / fb:.1%}",
                str(max(lengths)),
                f"{mean(lengths):.1f}",
                str(total_items),
                fmt(child_bytes // total_items) if total_items else "—",
            )
        console.print(at)

    # ── 3. Outlier lines with per-line top contributor ─────────────────────────
    console.print(Rule("[bold]3 · Fattest lines — top contributing path[/bold]"))
    lt = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
    lt.add_column("Line", justify="right")
    lt.add_column("Bytes", justify="right")
    lt.add_column("% file", justify="right")
    lt.add_column("Top path")
    lt.add_column("Path bytes", justify="right")
    lt.add_column("% line", justify="right")

    for lineno, line_bytes, top_path, top_bytes in sorted(stats.line_info, key=lambda x: x[1], reverse=True)[:outlier_n]:
        lt.add_row(
            str(lineno),
            fmt(line_bytes),
            f"{line_bytes / fb:.1%}",
            top_path,
            fmt(top_bytes),
            f"{top_bytes / line_bytes:.0%}" if line_bytes else "—",
        )
    console.print(lt)

    # ── 4. Deduplication candidates ────────────────────────────────────────────
    dedup: list[tuple[str, int, int, int]] = []  # (path, total_occ, unique_count, wasted_bytes)
    for norm_path, hash_counter in stats.path_hashes.items():
        total_occ = sum(hash_counter.values())
        unique_count = len(hash_counter)
        if total_occ < 2 or unique_count >= total_occ:
            continue
        wasted = sum(
            (stats.path_hash_bytes[norm_path][h] // count) * (count - 1)
            for h, count in hash_counter.items()
            if count > 1
        )
        if wasted > fb * 0.005:
            dedup.append((norm_path, total_occ, unique_count, wasted))

    if dedup:
        console.print(Rule("[bold]4 · Deduplication candidates[/bold]"))
        dt = Table(box=box.SIMPLE, show_header=True, header_style="bold cyan", padding=(0, 1))
        dt.add_column("Path")
        dt.add_column("Occurrences", justify="right")
        dt.add_column("Unique values", justify="right")
        dt.add_column("Redundancy", justify="right")
        dt.add_column("Wasted bytes", justify="right")
        dt.add_column("% file", justify="right")

        for norm_path, total_occ, unique_count, wasted in sorted(dedup, key=lambda x: x[3], reverse=True):
            dt.add_row(
                norm_path,
                str(total_occ),
                str(unique_count),
                f"{1 - unique_count / total_occ:.0%}",
                fmt(wasted),
                f"{wasted / fb:.1%}",
            )
        console.print(dt)

    # ── 5. Surgical cuts (synthesized) ────────────────────────────────────────
    console.print(Rule("[bold]5 · Recommended cuts — ranked by impact[/bold]"))
    cuts: list[tuple[str, str, int | None, int]] = []  # (kind, path, param, saved_bytes)

    # Best cap per string path
    cap_levels = [2_000, 5_000, 10_000, 20_000, 50_000, 100_000]
    for norm_path, sizes in stats.path_sizes.items():
        best_saved, best_cap = 0, cap_levels[0]
        for cap in cap_levels:
            s = savings_at_cap(sizes, cap)
            if s > best_saved:
                best_saved, best_cap = s, cap
        if best_saved > fb * 0.01:
            cuts.append(("cap_string", norm_path, best_cap, best_saved))

    # Drop and truncate per fat array
    for norm_path, (lengths, child_bytes) in fat_arrays.items():
        total_items = sum(lengths)
        avg_item_bytes = child_bytes / total_items if total_items else 0

        if child_bytes > fb * 0.01:
            cuts.append(("drop_array", norm_path, None, child_bytes))

        # Most conservative truncation that still saves > 1%
        for keep_n in [500, 100, 50, 10]:
            saved = int(sum(max(0, length - keep_n) * avg_item_bytes for length in lengths))
            if saved > fb * 0.01:
                cuts.append(("truncate_array", norm_path, keep_n, saved))
                break  # most conservative qualifying option

    # Dedup
    for norm_path, _occ, _unique, wasted in dedup:
        cuts.append(("dedup", norm_path, None, wasted))

    cuts.sort(key=lambda x: x[3], reverse=True)

    if not cuts:
        console.print("  No high-impact cuts found (all fields < 1% of file).\n")
        return

    for kind, norm_path, param, saved in cuts[:top_n]:
        pct = saved / fb * 100
        if kind == "cap_string":
            action = f"Cap [cyan]{norm_path}[/cyan] strings at {fmt(param)}"
        elif kind == "drop_array":
            action = f"Drop array [cyan]{norm_path}[/cyan] entirely"
        elif kind == "truncate_array":
            action = f"Truncate array [cyan]{norm_path}[/cyan] to first {param} items"
        else:
            action = f"Deduplicate [cyan]{norm_path}[/cyan]"
        console.print(f"  → {action}  saves ~[bold]{fmt(saved)}[/bold] ({pct:.1f}%)")

    console.print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic JSONL bloat scout. No shape assumptions.")
    parser.add_argument("file", help="Path to the JSONL file")
    parser.add_argument("--top", type=int, default=20, metavar="N", help="Rows per table (default: 20)")
    parser.add_argument("--outliers", type=int, default=10, metavar="N", help="Outlier lines to show (default: 10)")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {path}", file=sys.stderr)
        sys.exit(1)

    stats = Stats()
    stats.ingest(path)
    render(stats, top_n=args.top, outlier_n=args.outliers)


if __name__ == "__main__":
    main()
