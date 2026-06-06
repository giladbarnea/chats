# Known Bugs

2026-05-03: in Claude sessions, specifying `--agents` isn't sufficient to display agent prompts and outputs; `--tools` is also needed. It shouldn't. This is because internally, Claude's jsonl files represent agents as a kind of tool. But `ch` thinks of agents is a separate thing, so `--agents` should be enough. Example session: `9cf43d49-a500-45f8-9ed1-9a2254abe5df` 
