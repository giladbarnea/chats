---
name: architecture
description: Document the architecture of the `ccc` CLI tool.
last_updated: 2026-04-16, working tree after 3cd8c1b
---

# ARCHITECTURE.md

## Core Runtime Concepts

- `SessionPool` (`session_pool.py`): the per-invocation inventory of all supported session files. It owns the “one big pool” mental model for exact-id resolution and provider-aware search routing.
- `SessionScan` (`session_scan.py`): the one-pass per-file scan object used by search. It decodes one session once into `cwd`, summaries, custom titles, and already-visible messages.
- `SearchHit` (`commands.py`): the unit of successful search work. It carries the matched conversation’s lazily loaded metadata plus the already-scanned messages and match facets needed for display.
- `JsonlSessionAdapter` (`parsing.py`): the provider-owned path matcher/parser boundary. Adapter choice is path-based, not content-probed.

## Architecture Diagram (Space)

> Focus: The "City Map". Structural boundaries, where things "live", high-level grouping, and external relationships.
> Answers: What are the major building blocks of the system?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL WORLD                                                             │
│                                                                             │
│  ┌────────┐      ┌─────────────────────────────────┐      ┌──────────────┐  │
│  │  USER  │─────►│  CLI (ccc <subcommand> [args])  │◄─────│ stdin / pipe │  │
│  └────────┘      └────────────────┬────────────────┘      └──────────────┘  │
│                                   │                                         │
╞═══════════════════════════════════│═════════════════════════════════════════╡
│  CCC (System Boundary)            │                                         │
│                                   ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      CLI ROUTER (cli.py:main)                        │   │
│  │   argparse, visibility normalization, ConversationFlags builder      │   │
│  └──────────────────────────────────────┬───────────────────────────────┘   │
│                                         │                                   │
│  ┌──────────────────────────────────────▼────────────────────────────────┐  │
│  │                  COMMAND ORCHESTRATION (commands.py)                  │  │
│  │   cmd_parse  cmd_search  cmd_fork  cmd_rename  cmd_rm  cmd_catalog   │  │
│  └──────────────┬───────────────────────────────┬────────────────────────┘  │
│                 │                               │                           │
│  ┌──────────────▼─────────────┐   ┌─────────────▼────────────────────────┐  │
│  │ INVENTORY / ROUTING        │   │ CONTENT SCAN / SEARCH CONFIRMATION   │  │
│  │ session_pool.py            │   │ session_scan.py + commands.py        │  │
│  │  • SessionPool.discover()  │   │  • SessionScan.from_content()        │  │
│  │  • by_provider             │   │  • literal candidate pass            │  │
│  │  • by_stem / by_filename   │   │  • rendered-content confirmation     │  │
│  │  • exact-id resolution     │   │  • SearchHit + lazy metadata         │  │
│  └──────────────┬─────────────┘   └─────────────┬────────────────────────┘  │
│                 │                               │                           │
│  ┌──────────────▼────────────────────────────────▼────────────────────────┐  │
│  │                        PARSING LAYER (parsing.py)                      │  │
│  │  detect_format  decode_jsonl_entries  parse_jsonl_entries             │  │
│  │  extract_*_from_entries  parse_raw_cli_transcript                     │  │
│  │  JSONL session adapters: Claude / PI / Codex                          │  │
│  └──────────────┬─────────────────────────────────────────────────────────┘  │
│                 │                                                            │
│  ┌──────────────▼─────────────────────────────────────────────────────────┐  │
│  │                  MODEL + FORMATTING (model.py, formatting.py)         │  │
│  │  Message / ConversationFlags / render_message_inner_xml / format_*    │  │
│  └──────────────┬─────────────────────────────────────────────────────────┘  │
│                 │                                                            │
│  ┌──────────────▼─────────────────────────────────────────────────────────┐  │
│  │                         CATALOG MODULE (catalog/)                     │  │
│  │  catalog_sessions() -> cmd_parse() capture -> external claude CLI     │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
╞═════════════════════════════════════════════════════════════════════════════╡
│  EXTERNAL STORES                                                            │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │ ~/.claude/projects/  │  │ ~/.pi/agent/     │  │ ~/.codex/sessions/    │  │
│  │   */*.jsonl          │  │   sessions/*.jsonl│ │   *.jsonl             │  │
│  └──────────────────────┘  └──────────────────┘  └───────────────────────┘  │
│  ┌──────────────────────┐  ┌──────────────────┐                             │
│  │ ~/.claude/history.   │  │ sessions.yaml    │                             │
│  │   jsonl              │  │ (per-project)    │                             │
│  └──────────────────────┘  └──────────────────┘                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sequence Diagrams (Time)

### Feature 1: Parse (`ccc [input] [slice ...]`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ccc <input> [slice ...] [flags]`     ──► cli.py:main()
│
├───►  main()                   Detects no subcommand keyword              ──► argparse (default parse)
│      argparse                 Parses flags; handles edge cases:          ──► args namespace
│                               negative-index swap, tool/slice
│                               disambiguation, nargs='?' fixups
│
├───►  main()                   _normalize_parse_visibility_args(args)     ──► Resolves --only-user,
│                               Warns on contradictions                        --only-assistant, --no-*
│
├───►  main()                   _build_parse_flags(args)                   ──► ConversationFlags
│
├───►  main()                   cmd_parse(flags, input, slice, out, fmt)   ──► commands.py
│
├───►  cmd_parse                _resolve_input_content(input_arg)          ──► commands.py
│      │                        ├── _try_resolve_conversation_file()
│      │                        │   ├── Try Path(input).exists()
│      │                        │   ├── SessionPool.discover()/from_files()
│      │                        │   ├── is_single_negative_index()
│      │                        │   │   └── _resolve_recent_conversation_file()
│      │                        │   │       ├── _build_conversation_metadata()
│      │                        │   │       └── resolve_negative_index()
│      │                        │   ├── pool.resolve_exact_identifier()
│      │                        │   ├── UUID-like miss short-circuit
│      │                        │   ├── Summary prefix scan
│      │                        └── Read resolved path or passthrough raw input
│
├───►  cmd_parse                detect_format(content)                     ──► "jsonl" | "raw"
│
├───►  cmd_parse                parse_jsonl(content, flags, source_path)   ──► parsing.py
│      │                        ├── decode_jsonl_entries()
│      │                        ├── parse_jsonl_entries()
│      │                        ├── _select_jsonl_session_adapter()
│      │                        └── adapter-owned entry parser             ──► list[Message]
│                               OR
│      cmd_parse                parse_raw_cli_transcript(content, flags)   ──► list[Message]
│
├───►  cmd_parse                _merge_agent_messages() [if --agents]      ──► Merges agent timeline
│      │                        ├── find_agent_files_for_session()
│      │                        ├── _extract_task_dispatches(content)
│      │                        └── Sort + insert by timestamp
│
├───►  cmd_parse                _build_tool_id_map(messages)               ──► {tool_id: tool_name}
│
├───►  cmd_parse                parse_slice_notation(selector)             ──► (start, stop)
│      cmd_parse                OR matching selector positions             ──► sliced messages
│
├───►  cmd_parse                print_metadata() [if xml + not file out]   ──► stdout (YAML frontmatter)
│
├───►  cmd_parse                Format output:                             ──► formatted string
│      │                        ├── format_to_xml(messages, flags, map)
│      │                        ├── format_to_json(messages, flags, map)
│      │                        └── format_to_raw(messages, flags, map)
│
├───►  cmd_parse                Emit output:
│      │                        ├── output_file.write_text()               ──► File
│      │                        ├── print(formatted)                       ──► stdout (json/raw/no-color)
│      │                        └── render_messages_with_rich()            ──► Rich console (color)
│      │                            └── [pager if flags.paging]
│
└───►  User                     Sees formatted conversation
```

### Feature 2: Search (`ccc search <pattern>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ccc search <pattern> [flags]`        ──► cli.py:main()
│
├───►  main()                   Detects sys.argv[1] == "search"            ──► argparse (search parser)
│      argparse                 Parses: pattern, -l, -ll, -d, -ma,        ──► args namespace
│                               -ca, -T, -t, -a, -A, -s, --color, etc.
│
├───►  main()                   Builds ConversationFlags                   ──► flags
│      main()                   cmd_search(pattern, flags, list, ...)      ──► commands.py
│
├───►  cmd_search               parse_date_filter(mafter), (cafter)        ──► datetime | None
│
├───►  cmd_search               re.compile(pattern, IGNORECASE|...)        ──► regex
│                               Falls back to re.escape on invalid regex
│                               May also derive literal_candidate
│
├───►  cmd_search               SessionPool.discover(include_sidechains=   ──► pool
│                               flags.show_agents)
│      cmd_search               Route search files through pool.by_provider
│                               or pool.files
│
├───►  cmd_search               For each session file:
│      │                        ├── content = path.read_text()
│      │                        ├── _search_candidate_matches(content, ...)
│      │                        │   └── Cheap skip for plain-literal misses
│      │                        ├── _search_conversation_content(path, ...)
│      │                        │   ├── SessionScan.from_content()
│      │                        │   │   ├── detect_format()
│      │                        │   │   ├── decode_jsonl_entries()
│      │                        │   │   ├── extract_*_from_entries()
│      │                        │   │   └── parse_jsonl_entries() or raw parse
│      │                        │   ├── Apply dir_filter using scan.cwd
│      │                        │   ├── regex.search() summaries/titles
│      │                        │   ├── _build_tool_id_map(messages)
│      │                        │   └── regex.search(render_message_inner_xml(msg))
│      │                        ├── _load_conversation_metadata(path)
│      │                        ├── _passes_date_filters(meta, mafter, cafter)
│      │                        └── Build SearchHit
│
├───►  cmd_search               sort_by_modified(hits)                     ──► ordered SearchHit list
│
├───►  cmd_search               display_search_result() for each hit:
│      │                        ├── [--only-id]: print session ID only
│      │                        ├── print_metadata() (YAML frontmatter)
│      │                        ├── [--list]: stop after metadata
│      │                        └── render_messages_with_rich() or format_to_xml()
│
└───►  cmd_search               sys.exit(0 if found_any else 1)
```

### Feature 3: Rename (`ccc rename <id> <name>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ccc rename <id> <new_name>`          ──► cli.py:main()
│
├───►  main()                   Detects sys.argv[1] == "rename"            ──► argparse (rename parser)
│
├───►  main()                   cmd_rename(conversation_id, new_name)      ──► commands.py
│
├───►  cmd_rename               resolve_conversation_file(conv_id)         ──► Path (or exit)
│      │                        └── _try_resolve_conversation_file()
│
├───►  cmd_rename               get_native_session_id(conv_file)           ──► session_id string
│
├───►  cmd_rename               extract_cwd_from_jsonl(content)            ──► project path | None
│
├───►  cmd_rename               Append to conv_file:                       ──► .jsonl file
│      │                        ├── {"type":"custom-title","customTitle":name}
│      │                        └── {"type":"agent-name","agentName":name}
│
├───►  cmd_rename               Append to ~/.claude/history.jsonl:         ──► history.jsonl
│      │                        └── {"display":"/rename ...","sessionId":id}
│
└───►  cmd_rename               Print confirmation                         ──► console
```

### Feature 4: Remove (`ccc rm <session>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ccc rm <session> [--dry-run]`        ──► cli.py:main()
│
├───►  main()                   Detects sys.argv[1] == "rm"                ──► argparse (rm parser)
│
├───►  main()                   cmd_rm(session, dry_run=...)               ──► commands.py
│
├───►  cmd_rm                   _resolve_session_for_rm(session_id)        ──► Path (or exit)
│      │                        └── _try_resolve_conversation_file()
│
├───►  cmd_rm                   Determine if Claude session path           ──► bool
│      │                        └── _is_claude_session_path(conv_file)
│
├───►  cmd_rm                   Collect artifacts to remove:
│      │                        ├── _collect_session_files()
│      │                        │   ├── conv_file itself
│      │                        │   ├── find_agent_files_for_session()
│      │                        │   ├── debug/{uuid}.txt
│      │                        │   └── todos/{uuid}-agent-{uuid}.json
│      │                        ├── _collect_session_dirs()
│      │                        │   ├── file-history/{uuid}/
│      │                        │   ├── projects/{project}/{uuid}/
│      │                        │   └── session-env/{uuid}/
│      │                        └── _filter_history_lines()
│      │                            └── Filters history.jsonl by sessionId
│
├───►  cmd_rm                   _display_rm_preview()                      ──► console
│      │                        ├── Lists existing files with _file_meta()
│      │                        ├── Lists dirs with _render_dir_tree()
│      │                        └── Shows history lines to remove
│
├───►  cmd_rm                   [if --dry-run]: exit
│      cmd_rm                   [else]: input("Proceed? [y/n]")            ──► User confirmation
│
├───►  cmd_rm                   _execute_removal()                         ──► Filesystem
│      │                        ├── f.unlink() for each file
│      │                        ├── shutil.rmtree() for each dir
│      │                        └── history_file.write_text(filtered)
│
└───►  cmd_rm                   Print summary                              ──► console
```

### Feature 5: Catalog (`ccc catalog <args>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ccc catalog <session_ids|greppable>` ──► cli.py:main()
│                               (may also pipe content via stdin)
│
├───►  main()                   Detects sys.argv[1] == "catalog"           ──► cmd_catalog(argv[2:])
│      cmd_catalog              catalog_sessions(args)                     ──► catalog/__init__.py
│
├───►  catalog_sessions         Classify args:                             ──► session_ids, greppable
│      │                        ├── _is_session_id(arg) / _is_file_path()
│      │                        └── Read piped stdin if not tty
│
├───►  catalog_sessions         Extract session IDs from greppable text    ──► regex: session_id: <UUID>
│      │                        └── Fallback: _extract_metadata(piped)
│      │                            to get session_id from YAML frontmatter
│
├───►  catalog_sessions         For each session_id:
│      │
│      ├── _get_session_content(session_id)                                ──► str | None
│      │   └── cmd_parse(flags, session_id, format="xml",                  ──► captured stdout
│      │         emit_metadata=True) via redirect_stdout
│      │
│      ├── _extract_metadata(content)                                      ──► {session_id, directory, ...}
│      │   └── Parse YAML frontmatter between --- markers
│      │
│      ├── Resolve sessions.yaml path                                      ──► Path
│      │   ├── From metadata "directory" field
│      │   └── Fallback: ~/.claude/sessions.yaml
│      │
│      ├── Create sessions.yaml if missing                                 ──► File
│      │   └── Copy TEMPLATE_PATH or write minimal YAML
│      │
│      ├── Skip checks:
│      │   ├── Skip if session in yaml_data["ignored"]
│      │   └── Skip if updated_when_message_count_was unchanged
│      │
│      ├── Build prompt:                                                   ──► full_prompt string
│      │   ├── Tag session content in <attached-ai-session-for-cataloging>
│      │   └── Fill PROMPT_TEMPLATE with sessions_path
│      │
│      └── subprocess.run(                                                 ──► External Process
│          ["claude", "--model=sonnet",
│           "--dangerously-skip-permissions", "-p", full_prompt],
│          cwd=session_directory, env={OAUTH/API_KEY})
│
└───►  catalog_sessions         Print "Done."                              ──► console
```

---

## Data Flow Diagram (Matter)

```
[ RAW INPUT ]                 [ INVENTORY / RESOLUTION ]          [ SCAN / PARSE ]            [ OUTPUT ]
(ID / Path / stdin)           (SessionPool + helpers)             (SessionScan / Messages)    (Display)

                              ┌────────────────────────┐
Session UUID / filename ────► │ SessionPool           │
                              │  • by_stem            │
                              │  • by_filename        │
                              │  • native-id fallback │
                              └──────────┬────────────┘
                              ┌──────────▼────────────┐
Negative index (e.g. -1) ───► │ Metadata order path   │
                              │  • _build_conversation│
                              │    _metadata()        │
                              │  • resolve_negative_  │
                              │    index()            │
                              └──────────┬────────────┘
                              ┌──────────▼────────────┐
Summary prefix ─────────────► │ extract_summaries_    │
                              │ from_jsonl() scan     │
                              └──────────┬────────────┘
                                         │
                                         ▼
                               content string + source_path
                                         │
                           ┌─────────────▼─────────────┐
                           │ detect_format()           │
                           │  ├─ jsonl                 │
                           │  │   ├─ decode entries    │
                           │  │   ├─ extract cwd /     │
                           │  │   │   summaries /      │
                           │  │   │   custom titles    │
                           │  │   └─ parse_jsonl_      │
                           │  │       entries()        │
                           │  └─ raw transcript        │
                           └─────────────┬─────────────┘
                                         │
                          parse path ────┼────► visible Message objects
                                         │             │
                                         │             ├── slice
                                         │             ├── tool-id map
                                         │             └── format_to_* / Rich
                                         │
                          search path ───┼────► candidate prefilter
                                         │             │
                                         │             ├── summaries / titles regex
                                         │             ├── render_message_inner_xml()
                                         │             ├── lazy metadata load
                                         │             └── SearchHit display
                                         │
                          rename path ───┼────► append custom-title / agent-name
                                         │
                          rm path ───────┼────► collect artifacts + delete
                                         │
                          catalog path ──┴────► cmd_parse capture -> claude CLI
```

---

## State Machines

### Session Resolution State Machine

```
                        ┌─────────────┐
            input ─────►│  Raw Input  │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐     yes
                        │  Is valid   │──────────► RESOLVED (Path)
                        │  file path? │
                        └──────┬──────┘
                               │ no
                        ┌──────▼──────────┐
                        │ Build / reuse   │
                        │ SessionPool     │
                        └──────┬──────────┘
                               │
                        ┌──────▼──────────┐  yes
                        │ Is negative     │──────► _build_conversation_metadata()
                        │ index (-N)?     │        → resolve_negative_index()
                        └──────┬──────────┘        → RESOLVED (Path) or NOT_FOUND
                               │ no
                        ┌──────▼──────────┐  yes
                        │ Single word?    │──────► pool.resolve_exact_identifier()
                        │ Exact ID/name?  │        → RESOLVED (Path)
                        └──────┬──────────┘          or fall through
                               │ no match
                        ┌──────▼──────────┐  yes
                        │ UUID-like miss? │──────► NOT_FOUND (fast fail)
                        └──────┬──────────┘
                               │ no
                        ┌──────▼──────────┐  1 match
                        │ Summary prefix  │──────────► RESOLVED (Path)
                        │ search (case-   │  >1 match
                        │ insensitive)    │──────────► AMBIGUOUS (error)
                        └──────┬──────────┘
                               │ 0 matches
                               ▼
                          NOT_FOUND (error)
```

### Parse Feature State Machine

```
         ┌──────────┐        ┌──────────────┐       ┌────────────────┐
  input──►│ RESOLVE  │───────►│ DETECT &     │──────►│ POST-PROCESS   │
         │ session  │        │ PARSE        │       │                │
         └──────────┘        │              │       │ • merge agents │
              │              │ jsonl:       │       │ • build tool   │
          NOT_FOUND──►exit   │  adapter     │       │   id map       │
                             │  dispatch    │       │ • apply slice  │
                             │ raw:         │       └───────┬────────┘
                             │  transcript  │               │
                             │  parser      │       ┌───────▼────────┐
                             └──────────────┘       │ FORMAT &       │
                                                    │ EMIT           │
                                                    │                │
                                                    │ xml → stdout   │
                                                    │ json → stdout  │
                                                    │ raw → stdout   │
                                                    │ color → Rich   │
                                                    │ file → write   │
                                                    └────────────────┘
```

### Search Feature State Machine

```
         ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
  args───►│ COMPILE      │─────►│ BUILD        │─────►│ ITERATE      │
         │ regex +      │      │ SessionPool  │      │ search_files │
         │ literal hint │      │ + provider   │      └──────┬───────┘
         └──────────────┘      │ routing      │             │
                               └──────────────┘      ┌──────▼────────────┐
                                                     │ Per file:         │
                                                 no  │ candidate pass?   │──► SKIP
                                                     └──────┬────────────┘
                                                            │ yes
                                                     ┌──────▼────────────┐
                                                 no  │ dir filter passes?│──► SKIP
                                                     └──────┬────────────┘
                                                            │ yes
                                                     ┌──────▼────────────┐
                                                     │ SessionScan +     │
                                                     │ regex search over │
                                                     │ summaries, titles,│
                                                     │ rendered messages │
                                                     └──────┬────────────┘
                                                            │
                                                 no         │ any match
                                            SKIP ◄──────────┘
                                                            │ yes
                                                     ┌──────▼────────────┐
                                                 no  │ metadata passes   │──► SKIP
                                                     │ date filters?     │
                                                     └──────┬────────────┘
                                                            │ yes
                                                     ┌──────▼────────────┐
                                                     │ collect SearchHit │
                                                     └──────┬────────────┘
                                                            │
                                        none found ──► exit(1)
                                                            │
                                                     ┌──────▼────────────┐
                                                     │ sort hits by      │
                                                     │ modified time     │
                                                     └──────┬────────────┘
                                                            │
                                                     ┌──────▼────────────┐
                                                     │ DISPLAY / exit(0) │
                                                     └───────────────────┘
```

### Remove Feature State Machine

```
         ┌──────────┐      ┌──────────────┐      ┌──────────────┐
  id ───►│ RESOLVE  │─────►│ COLLECT      │─────►│ PREVIEW      │
         │ session  │      │ artifacts    │      │ display      │
         └──────────┘      │              │      └──────┬───────┘
              │            │ • files      │             │
          NOT_FOUND──►exit │ • dirs       │      ┌──────▼───────┐
                           │ • history    │  yes │ --dry-run?   │──► EXIT (no changes)
                           └──────────────┘      └──────┬───────┘
                                                        │ no
                                                 ┌──────▼───────┐
                                             n   │ User confirm │──► EXIT (cancelled)
                                                 │ [y/n]?       │
                                                 └──────┬───────┘
                                                        │ y
                                                 ┌──────▼───────┐
                                                 │ EXECUTE      │
                                                 │ • unlink     │
                                                 │ • rmtree     │
                                                 │ • rewrite    │
                                                 │   history    │
                                                 └──────────────┘
```

### Catalog Feature State Machine

```
                 ┌───────────────┐       ┌──────────────────┐
  args/stdin ───►│ CLASSIFY      │──────►│ EXTRACT IDs      │
                 │ • session IDs │       │ • from greppable │
                 │ • greppable   │       │   text (regex)   │
                 │ • piped stdin │       │ • from YAML      │
                 └───────────────┘       │   frontmatter    │
                                         └────────┬─────────┘
                                                  │
                                  no IDs ──► exit(1)
                                                  │
                                         ┌────────▼─────────┐
                                         │ First session_id │
                                         │ only:            │
                                         └────────┬─────────┘
                                                  │
                                         ┌────────▼─────────┐
                                     no  │ Get content?     │──► exit
                                         │ _get_session_    │
                                         │ content() or     │
                                         │ preloaded        │
                                         └────────┬─────────┘
                                                  │ yes
                                         ┌────────▼─────────┐
                                         │ Resolve dir +    │
                                         │ sessions.yaml    │
                                         │ path             │
                                         └────────┬─────────┘
                                                  │
                                         ┌────────▼─────────┐
                                     yes │ In ignored[]?    │──► SKIP
                                         └────────┬─────────┘
                                                  │ no
                                         ┌────────▼─────────┐
                                     yes │ Message count    │──► SKIP (unchanged)
                                         │ unchanged?       │
                                         └────────┬─────────┘
                                                  │ no / new
                                         ┌────────▼─────────┐
                                         │ Build prompt +   │
                                         │ subprocess.run   │──► claude CLI
                                         │ (claude --model  │    modifies sessions.yaml
                                         │  sonnet -p ...)  │
                                         └─────────────────┘
```

---

## Call Graph (Logic)

```
cli.py:main()
├── init_module_console_from_color_arg()
│   └── console.init_module_console()
│
├── [subcommand dispatch]
│   ├── sys.argv[1] == "search" → argparse → cmd_search()
│   ├── sys.argv[1] == "fork"   → argparse → cmd_fork()
│   ├── sys.argv[1] == "rename" → argparse → cmd_rename()
│   ├── sys.argv[1] == "rm"     → argparse → cmd_rm()
│   ├── sys.argv[1] == "catalog"→ cmd_catalog(sys.argv[2:])
│   └── default                 → argparse → cmd_parse()
│
├── [parse mode only]
│   ├── _resolve_thinking_mode(raw_thinking, show_all)
│   ├── _resolve_show_tools(raw_tools, show_all)
│   │   └── parse_tool_spec(spec) → ToolFilter
│   ├── _normalize_parse_visibility_args(args)
│   │   └── _warn_only_override()
│   ├── _build_parse_flags(args) → ConversationFlags
│   └── is_single_negative_index(candidate)
│
cmd_parse(flags, input_arg, slice_str, output_file, output_format, emit_metadata)
├── _resolve_input_content(input_arg)
│   ├── _try_resolve_conversation_file(identifier)
│   │   ├── Path(identifier).exists()
│   │   ├── SessionPool.discover() / SessionPool.from_files()
│   │   ├── is_single_negative_index(identifier)
│   │   │   └── _resolve_recent_conversation_file(identifier, files)
│   │   │       ├── _build_conversation_metadata(files)
│   │   │       └── resolve_negative_index(identifier, ordered)
│   │   ├── pool.resolve_exact_identifier(identifier)
│   │   ├── UUID-like miss short-circuit
│   │   └── extract_summaries_from_jsonl(conv_file)
│   ├── resolved_path.read_text()
│   └── stdin.read() / raw input passthrough
├── detect_format(content) → "jsonl" | "raw"
├── parse_jsonl(content, flags, source_path) / parse_raw_cli_transcript(content, flags)
│   └── parse_jsonl_entries(entries, flags, source_path)
│       └── adapter-owned entry parser
├── _merge_agent_messages(messages, content, input_file_path, flags) [if --agents]
├── _build_tool_id_map(messages)
├── normalize one-or-more slice selectors
├── parse_slice_notation(selector) for each selector
├── _load_conversation_metadata(input_file_path) / print_metadata(...)
└── format_to_xml/json/raw(...) or render_messages_with_rich(...)

cmd_search(pattern, flags, list_only, only_id, dir_filter, mafter, cafter)
├── parse_date_filter(mafter) / parse_date_filter(cafter)
├── re.compile(pattern) + literal_candidate
├── SessionPool.discover(include_sidechains=flags.show_agents)
├── choose search_files via pool.by_provider[provider] or pool.files
├── for each file → _search_hit_for_file(...)
│   ├── conv_file.read_text()
│   ├── _search_candidate_matches(content, pattern_arg, literal_candidate, flags)
│   ├── _search_conversation_content(conv_file, content, regex, flags, dir_filter)
│   │   ├── SessionScan.from_content(content, flags, source_path=conv_file)
│   │   │   ├── detect_format()
│   │   │   ├── decode_jsonl_entries()
│   │   │   ├── extract_cwd_from_entries()
│   │   │   ├── extract_summaries_from_entries()
│   │   │   ├── extract_custom_titles_from_entries()
│   │   │   └── parse_jsonl_entries() / parse_raw_cli_transcript()
│   │   ├── dir filter against scan.cwd
│   │   ├── regex.search(summary/title)
│   │   ├── _build_tool_id_map(messages)
│   │   └── regex.search(render_message_inner_xml(msg, ...))
│   ├── _load_conversation_metadata(conv_file)
│   └── _passes_date_filters(meta, mafter_dt, cafter_dt)
├── sort_by_modified(hits, modified_at=lambda hit: hit.metadata.mtime)
└── display_search_result(...)

cmd_fork(session_id, flags)
├── resolve_conversation_file(session_id)
└── fork_session(conv_file, flags)

cmd_rename(conversation_id, new_name)
├── resolve_conversation_file(conversation_id)
├── get_native_session_id()
├── extract_cwd_from_jsonl()
├── json.dumps() → append `custom-title` to conv_file
├── json.dumps() → append `agent-name` to conv_file
└── json.dumps() → append `/rename ...` to history.jsonl

cmd_rm(session_id, dry_run)
├── _resolve_session_for_rm()
│   └── _try_resolve_conversation_file()
├── _is_claude_session_path()
├── _collect_session_files()
│   └── find_agent_files_for_session()
├── _collect_session_dirs()
├── _filter_history_lines()
├── _display_rm_preview()
│   ├── _file_meta()
│   │   ├── _human_size()
│   │   └── _line_count()
│   ├── _render_dir_tree()
│   └── collapse_home()
└── _execute_removal()
    └── shutil.rmtree()

cmd_catalog(args)
└── catalog_sessions(args)
    ├── _is_session_id() / _is_file_path()
    ├── re.findall(session_id pattern)
    ├── _extract_metadata() [YAML frontmatter]
    ├── _get_session_content(session_id)
    │   └── cmd_parse(flags, session_id, format="xml")
    │       [via redirect_stdout → StringIO]
    ├── yaml.safe_load(sessions.yaml)
    ├── TEMPLATE_PATH.read_text() [if creating new]
    └── subprocess.run(["claude", "--model=sonnet", "-p", prompt])
```

---

## Module Dependency Map

```
cli.py
├── commands.py
│   ├── console.py
│   ├── date_filters.py
│   ├── forking.py
│   ├── formatting.py
│   ├── model.py
│   ├── ordering.py
│   ├── parsing.py
│   ├── session_pool.py
│   ├── session_scan.py
│   └── utils.py
├── formatting.py
│   ├── console.py
│   ├── model.py
│   ├── parsing.py
│   ├── tools.py
│   └── utils.py
├── parsing.py
│   ├── model.py
│   └── utils.py
├── session_pool.py
│   ├── model.py
│   └── parsing.py
├── session_scan.py
│   ├── model.py
│   └── parsing.py
├── console.py
├── model.py
├── ordering.py
├── tool_filter.py
└── catalog/
    ├── __init__.py
    │   ├── commands.py
    │   ├── console.py
    │   └── model.py
    └── assets/
        └── sessions.template.yaml
```

---

## Architecture Notes & Edge Cases (Shared Invariants / Non-obvious Behaviors)

1. **Adapter Selection Is Path-Based**: `parse_jsonl_entries()` chooses the provider adapter from `source_path`, not by probing payload shape. Raw stdin JSONL with no source path falls through to the default adapter.
2. **`SessionPool` Owns Inventory, Not Full Truth**: `SessionPool` is the unified inventory/routing layer for exact-id resolution and provider-aware search. It does not currently replace every metadata-heavy path.
3. **Recent Negative Indices Still Use Metadata Timestamps**: `_resolve_recent_conversation_file()` still goes through `_build_conversation_metadata()` and in-band timestamps rather than `SessionPool.stat_mtime_sorted`. The pool’s stat ordering exists, but parse recency is not yet driven by it.
4. **Parse Resolves Input Once**: `_resolve_input_content()` returns `(content, source_path)` so parse mode does not perform a second full resolution pass after reading stdin/path input.
5. **Search Semantics Are Visibility-Dependent**: `cmd_search` matches summaries, custom titles, and the rendered XML of visible message content. If tools, thinking, agents, or plans are hidden by flags, they do not count as matches.
6. **`--agents` Changes the Search Universe**: search does not merely render more content when `-a/--agents` is enabled; it discovers more files by including Claude sidechain sessions in the `SessionPool`.
7. **Candidate Pass Is an Optimization, Not New Semantics**: plain-literal queries first go through `_search_candidate_matches()`, but every surviving file still gets the normal rendered-content confirmation pass. Render-dependent patterns bypass the candidate shortcut entirely.
8. **Search Metadata Is Lazy**: `_load_conversation_metadata()` is paid only after a file has a content hit. Date filters still apply, but only to candidate hits rather than the entire search universe up front.
9. **Metadata Message Counts After Slicing**: parse-mode metadata reports `len(messages)` after slice application, not the original conversation length.
10. **Tool ID Map Lifecycle**: `_build_tool_id_map()` is deliberately called before parse-mode slicing so that a surviving `tool_result` can still resolve the display name of a sliced-out `tool_use`.
11. **Agent Merge Heuristics**: `_merge_agent_messages()` performs a timestamp-based merge of Claude sidechains into the main timeline. It infers placement from `Task` dispatch timing rather than a strict relational join.
12. **Catalog API Coupling**: `catalog` captures `cmd_parse()` stdout as an internal API boundary, then shells out to an external `claude` process for summarization.
13. **Asymmetrical Removal**: `cmd_rm` is Claude-heavy. Native Claude sessions lose sidecar artifacts, history lines, and directories; PI/Codex sessions currently resolve to deleting the single JSONL file.
