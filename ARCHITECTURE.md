---
name: architecture
description: Document the architecture of the `ccc` CLI tool.
last_updated: 2026-04-16, working tree after 3cd8c1b
---

# ARCHITECTURE.md

## Core Runtime Concepts

- `SessionPool` (`session_pool.py`): the per-invocation inventory of all supported session files. It owns the "one big pool" mental model for exact-id resolution and provider-aware search routing.
- `SessionScan` (`session_scan.py`): the one-pass per-file scan object used by search. It decodes one session once into `cwd`, summaries, the current latest custom title, and already-visible messages.
- `SearchHit` (`commands/search.py`): the unit of successful search work. It carries the matched conversation's lazily loaded metadata plus the already-scanned messages and match facets needed for display.
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
│  │                  COMMAND ORCHESTRATION (commands/)                    │  │
│  │   cmd_parse  cmd_search  cmd_fork  cmd_rename  cmd_rm  cmd_catalog   │  │
│  └──────────────┬───────────────────────────────┬────────────────────────┘  │
│                 │                               │                           │
│  ┌──────────────▼─────────────┐   ┌─────────────▼────────────────────────┐  │
│  │ INVENTORY / ROUTING        │   │ CONTENT SCAN / SEARCH CONFIRMATION   │  │
│  │ session_pool.py            │   │ session_scan.py + commands/search.py │  │
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
│  │  catalog_sessions() -> cmd_parse() capture -> external pi CLI        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
╞═════════════════════════════════════════════════════════════════════════════╡
│  EXTERNAL STORES                                                            │
│  ┌──────────────────────┐  ┌──────────────────┐  ┌───────────────────────┐  │
│  │ ~/.claude/projects/  │  │ ~/.pi/agent/     │  │ ~/.codex/sessions/    │  │
│  │   */*.jsonl          │  │   sessions/*.jsonl│ │   **/*.jsonl          │  │
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
│                               disambiguation, provider-scoped
│                               recent indices, nargs='?' fixups
│
├───►  main()                   _normalize_parse_visibility_args(args)     ──► Resolves --only-user,
│                               Warns on contradictions                        --only-assistant, --no-*
│
├───►  main()                   _build_parse_flags(args)                   ──► ConversationFlags
│
├───►  main()                   cmd_parse(flags, input, slice, out, fmt,   ──► commands/
│                               only_metadata, only_id)
│
├───►  cmd_parse                _resolve_input_content(input_arg)          ──► commands/resolve.py
│      │                        ├── _try_resolve_conversation_file()
│      │                        │   ├── Try Path(input).exists()
│      │                        │   ├── SessionPool.discover()/from_files()
│      │                        │   ├── is_single_negative_index()
│      │                        │   │   └── _resolve_recent_conversation_file()
│      │                        │   │       ├── Applies provider filter if supplied
│      │                        │   │       ├── Walks newest-first by stat mtime
│      │                        │   │       ├── pool_filter.passes_path_for_index() (cwd)
│      │                        │   │       ├── pool_filter.passes_path_for_date() (mtime/ctime)
│      │                        │   │       └── short-circuits at the Nth match
│      │                        │   ├── pool.resolve_exact_identifier()
│      │                        │   ├── UUID-like miss short-circuit
│      │                        │   ├── Summary prefix scan
│      │                        └── Read resolved path or passthrough raw input
│
├───►  cmd_parse                [if --only-id] print session ID + exit     ──► stdout / file
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
├───►  cmd_parse                [if --only-metadata] emit frontmatter +    ──► stdout / file
│                               exit
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
│                               -ca, -f, -T, -t, -a, -A, -s, --color, etc.
│
├───►  main()                   Builds ConversationFlags + PoolFilter      ──► flags, pool_filter
│      main()                   cmd_search(pattern, flags, pool_filter, ...) ──► commands/
│
├───►  cmd_search               re.compile(pattern, IGNORECASE|...)        ──► regex
│                               Falls back to re.escape on invalid regex
│                               May also derive literal_candidate
│
├───►  cmd_search               SessionPool.discover(include_sidechains=   ──► pool
│                               flags.show_agents)
│      cmd_search               pool_filter.candidate_files(pool)          ──► provider-narrowed files
│
├───►  cmd_search               For each session file:
│      │                        ├── [if -ma/-ca active]:
│      │                        │   └── pool_filter.passes_path_for_date(path) → skip pre-parse
│      │                        ├── [if -d active]:
│      │                        │   └── pool_filter.passes_path_for_index(path) → skip pre-parse
│      │                        ├── content = path.read_text()
│      │                        ├── _search_candidate_matches(content, ...)
│      │                        │   └── Cheap skip for plain-literal misses
│      │                        ├── _search_conversation_content(path, ..., pool_filter)
│      │                        │   ├── SessionScan.from_content()
│      │                        │   │   ├── detect_format()
│      │                        │   │   ├── decode_jsonl_entries()
│      │                        │   │   ├── extract_*_from_entries()
│      │                        │   │   └── parse_jsonl_entries() or raw parse
│      │                        │   ├── pool_filter.passes_cwd(scan.cwd)
│      │                        │   ├── regex.search() summaries/titles
│      │                        │   ├── _build_tool_id_map(messages)
│      │                        │   └── regex.search(render_message_inner_xml(msg))
│      │                        ├── [if metadata not yet loaded]: _load_conversation_metadata(path)
│      │                        └── Build SearchHit
│
├───►  cmd_search               sort_by_modified_descending(hits)          ──► ordered SearchHit list
│
├───►  cmd_search               display_search_result() for each hit:
│      │                        ├── [--only-id]: print session ID only
│      │                        ├── [--raw]: plain markdown output
│      │                        ├── print_metadata() (YAML frontmatter)
│      │                        ├── [--list]: stop after metadata
│      │                        ├── default: render matching messages
│      │                        └── [--full]: render all visible messages
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
├───►  main()                   cmd_rename(conversation_id, new_name)      ──► commands/
│
├───►  cmd_rename               resolve_conversation_file(conv_id)         ──► Path (or exit)
│      │                        └── _try_resolve_conversation_file()
│
├───►  cmd_rename               get_native_session_id(conv_file)           ──► session_id string
│      cmd_rename               get_jsonl_session_adapter(conv_file)       ──► provider adapter
│
├───►  cmd_rename               extract_cwd_from_jsonl(content)            ──► project path | None
│      cmd_rename               decode_jsonl_entries(content)              ──► parsed entries
│
├───►  cmd_rename               adapter.build_rename_entries(...)          ──► provider-native rename records
│      │                        ├── Claude: custom-title + agent-name
│      │                        ├── Codex: event_msg(thread_name_updated)
│      │                        └── PI: session_info(name)
│
├───►  cmd_rename               Append provider-native entries to conv_file ─► .jsonl file
│
├───►  cmd_rename               [Claude only] append /rename ... to        ──► ~/.claude/history.jsonl
│      │                        history.jsonl
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
├───►  main()                   cmd_rm(session, dry_run=...)               ──► commands/
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
├───►  catalog_sessions         Classify args:                             ──► session_id, greppable
│      │                        ├── _is_session_id(arg) / _is_file_path()
│      │                        ├── Read piped stdin if not tty
│      │                        └── Extract session ID from greppable
│      │                            (regex on session_id: <UUID>,
│      │                             or _extract_metadata fallback)
│
├───►  catalog_sessions         Resolve single session ID:                ──► session_id | exit(1)
│      │                        _resolve_session_id(args, piped_content)
│
├───►  catalog_sessions         Catalog that session:
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
│          ["pi", "--model=google/gemini-3-flash-preview",
│           "--thinking=high", "--print",
│           "--system-prompt", full_prompt],
│          cwd=session_directory)
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
                           │  │   │   current title    │
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
                          rename path ───┼────► append provider-native rename entry/entries
                                         │
                          rm path ───────┼────► collect artifacts + delete
                                         │
                          catalog path ──┴────► cmd_parse capture -> pi CLI
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
                        │ Is negative     │──────► provider scope (optional)
                        │ index (-N)?     │        → walk newest-first by stat mtime
                        │                 │        → cheap predicates (cwd, date)
                        └──────┬──────────┘        → RESOLVED (Path) or NOT_FOUND
                               │ no
                        ┌──────▼──────────┐  yes
                        │ Single word?    │──────► pool.resolve_exact_identifier()
                        │ Exact ID/name?  │        → RESOLVED (Path)
                        └──────┬──────────┘          or fall through
                               │ no match
                        ┌──────▼──────────┐  1 match
                        │ Current title   │──────────► RESOLVED (Path)
                        │ substring scan  │  >1 match
                        │ (latest only)   │──────────► AMBIGUOUS (error)
                        └──────┬──────────┘
                               │ 0 matches
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
  args/stdin ───►│ RESOLVE       │──────►│ _resolve_session_│
                 │ single        │       │ id():            │
                 │ session ID    │       │ • arg or file    │
                 │               │       │ • greppable UUID │
                 └───────────────┘       │ • piped stdin    │
                                         └────────┬─────────┘
                                                  │
                                  no ID ──► exit(1)
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
                                         │ subprocess.run   │──► pi CLI
                                         │ (pi --model=...  │    modifies sessions.yaml
                                         │  --print ...)    │
                                         └─────────────────┘
```

---

## Call Graph (Logic)

```
cli.py:main()
│
├── [subcommand dispatch]
│   ├── "search" → argparse → cmd_search()
│   ├── "fork"   → argparse → cmd_fork()
│   ├── "rename" → argparse → cmd_rename()
│   ├── "rm"     → argparse → cmd_rm()
│   ├── "catalog"→ cmd_catalog(argv[2:])
│   └── default  → argparse → cmd_parse()
│
├── [parse mode]
│   ├── Build ConversationFlags (visibility, thinking, tools, agents, plans)
│   ├── Build PoolFilter (provider, dir, date filters)
│   └── cmd_parse(flags, input, slices, output, pool_filter, output_mode)
│
│       1. Resolve input → (content, source_path)
│          Session pool, negative indices, exact IDs, summary prefixes
│       2. Detect format (jsonl vs raw transcript)
│       3. Parse → list[Message] via provider adapter
│       4. Merge agents, build tool-id map, apply slices
│       5. Format & emit (xml/json/raw, stdout/file, Rich/plain)
│
├── [search mode]
│   ├── Build ConversationFlags + PoolFilter
│   └── cmd_search(pattern, flags, pool_filter, output_mode)
│
│       1. Compile regex, derive literal candidate
│       2. SessionPool.discover() → candidate files
│       3. Per-file: candidate prefilter → SessionScan → regex confirm
│       4. Collect SearchHit objects, sort by modified time
│       5. Display (matches-only / full, metadata, id-only)
│
├── [fork mode]
│   └── cmd_fork(session_id, flags)
│       resolve → fork_session() → write provider-native fork
│
├── [rename mode]
│   └── cmd_rename(session_id, name)
│       resolve → adapter.build_rename_entries() → append to file
│
├── [rm mode]
│   └── cmd_rm(session_id, dry_run)
│       resolve → collect artifacts (files, dirs, history)
│       → preview → confirm → execute removal
│
└── [catalog mode]
    └── cmd_catalog(args)
        catalog_sessions(): classify args → get content via cmd_parse
        → build prompt → shell out to pi CLI → update sessions.yaml
```

---

## Module Dependency Map

```
cli.py
├── commands/
│   ├── parse.py      → model, parsing, formatting, console, ordering, utils
│   ├── search.py     → model, parsing, formatting, session_scan, console, ordering
│   ├── rename.py     → model, parsing, formatting, console
│   ├── resolve.py    → model, parsing, session_pool, ordering, utils
│   ├── rm.py         → model, parsing, console, utils
│   └── common.py     → model
├── catalog/          → commands, console, model
├── formatting.py     → model, parsing, console, tools, utils
├── parsing.py        → model, utils
├── session_pool.py   → model, parsing
├── session_scan.py   → model, parsing, ordering, pool_filter
├── forking.py        → model, parsing, utils
├── tool_filter.py
├── pool_filter.py    → model, parsing
├── console.py
├── model.py          → utils
├── ordering.py
├── lexer.py          (XmlmdLexer — rendering grammar)
├── parts.py          (MessagePart, ContentBlockType — structured message model)
├── registry.py       (ToolSchema, normalize_tool_name — tool normalization)
└── theme.py          (Rich theme definitions)
```

---

## Architecture Notes & Edge Cases (Shared Invariants / Non-obvious Behaviors)

1. **Adapter Selection Is Path-Based**: `parse_jsonl_entries()` chooses the provider adapter from `source_path`, not by probing payload shape. Raw stdin JSONL with no source path falls through to the default adapter.
2. **`SessionPool` Owns Inventory, Not Full Truth**: `SessionPool` is the unified inventory/routing layer for exact-id resolution and provider-aware search. It does not currently replace every metadata-heavy path.
3. **Recent Negative Indices Use Stat Mtime With Cheap Predicates**: `_resolve_recent_conversation_file()` walks candidates newest-first by `stat().st_mtime` and applies `PoolFilter.passes_path_for_index` (cwd) and `passes_path_for_date` (mtime/ctime) per candidate, short-circuiting at the Nth match. This unifies the dir-only fast path and the older metadata-eager slow path. The trade-off is that "newest" is always filesystem mtime, never in-band semantic mtime.
4. **Parse Resolves Input Once**: `_resolve_input_content()` returns `(content, source_path)` so parse mode does not perform a second full resolution pass after reading stdin/path input.
5. **Search Semantics Are Visibility-Dependent**: `cmd_search` matches summaries, the current latest custom title, and the rendered XML of visible message content. If tools, thinking, agents, or plans are hidden by flags, they do not count as matches.
6. **`--agents` Changes the Search Universe**: search does not merely render more content when `-a/--agents` is enabled; it discovers more files by including Claude sidechain sessions in the `SessionPool`.
7. **Candidate Pass Is an Optimization, Not New Semantics**: plain-literal queries first go through `_search_candidate_matches()`, but every surviving file still gets the normal rendered-content confirmation pass. Render-dependent patterns bypass the candidate shortcut entirely.
8. **Search Metadata Is Lazy**: `_load_conversation_metadata()` is paid only after a file has a content hit. Date filters still apply, but only to candidate hits rather than the entire search universe up front.
9. **Search Output Mode Separates Match Semantics From Display Breadth**: `SessionScan` and regex confirmation always determine the matching conversation first. `SearchOutputMode.MATCHES` renders only `hit.matches` (the default), while `SearchOutputMode.FULL` renders `hit.messages`, including summary/current-title-only hits.
10. **Search Raw Output Is Formatting-Only**: `search -r/--raw` does not change match semantics or breadth semantics. It reuses the same `SearchOutputMode` decision, then formats the chosen messages as plain markdown instead of Rich/XML.
11. **Optional Metadata Stays Sparse**: provider-owned metadata extractors may populate optional fields like `forked_from`, but `print_metadata()` omits absent values instead of rendering null-like placeholders.
12. **Metadata Message Counts After Slicing**: parse-mode metadata reports `len(messages)` after slice application, not the original conversation length.
13. **Tool ID Map Lifecycle**: `_build_tool_id_map()` is deliberately called before parse-mode slicing so that a surviving `tool_result` can still resolve the display name of a sliced-out `tool_use`.
14. **Agent Merge Heuristics**: `_merge_agent_messages()` performs a timestamp-based merge of Claude sidechains into the main timeline. It infers placement from `Task` dispatch timing rather than a strict relational join.
15. **Catalog API Coupling**: `catalog` captures `cmd_parse()` stdout as an internal API boundary, then shells out to an external `claude` process for summarization.
16. **Shared Session-Title Semantics**: metadata/resolution/search treat provider-native session-name records as one current-title abstraction: Claude `custom-title`, Codex `event_msg.payload.thread_name` when `payload.type == "thread_name_updated"`, and PI `session_info.name`. Only the latest title is acknowledged; historical titles are ignored.
17. **Parse Pool-Filter Scope**: parse-mode `-p/--provider`, `-d/--dir`, `-ma/--mafter`, `-ca/--cafter` narrow only recent negative-index lookup. Exact identifiers, file paths, summary prefixes, and stdin stay unfiltered; the CLI warns when any of these flags would otherwise be ignored. The four flags share a single declarative `PoolFilter` consumed by both `cmd_parse` and `cmd_search`, installed via `add_pool_filter_args`.
18. **Asymmetrical Removal**: `cmd_rm` is Claude-heavy. Native Claude sessions lose sidecar artifacts, history lines, and directories; PI/Codex sessions currently resolve to deleting the single JSONL file.
