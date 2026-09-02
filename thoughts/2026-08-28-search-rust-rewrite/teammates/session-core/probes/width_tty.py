import os
import sys

from rich.console import Console

console = Console()
print(
    f"stdout_isatty={sys.stdout.isatty()} "
    f"COLUMNS={os.environ.get('COLUMNS')!r} "
    f"rich_width={console.size.width}"
)
