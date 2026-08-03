---
name: architecture
description: Document the architecture of the `ch` CLI tool.
last_updated: 2026/08/03
---

# ARCHITECTURE.md

## Core Runtime Concepts

- `SessionPool` (`session_pool.py`): the per-invocation inventory of all supported session files. It owns the "one big pool" mental model for exact-id resolution and provider-aware search routing.
- `SessionScan` (`session_scan.py`): the one-pass per-file scan object used by search. It decodes one session once into `cwd`, summaries, the current latest custom title, and already-visible messages.
- `SearchHit` (`commands/search.py`): the unit of successful search work. It carries the matched conversation's lazily loaded metadata plus the already-scanned messages and match facets needed for display.
- `SearchQuery` (`search_query.py`): the parsed search pattern — a single `SearchTerm` or a boolean `AndQuery`/`OrQuery`/`NotQuery` tree over terms. Owns tokenizing, `and`/`or`/`not` grammar, and per-term regex/literal compilation under the selected case-sensitivity mode.
- `JsonlSessionAdapter` (`parsing.py`): the provider-owned path matcher/parser boundary. Adapter choice is path-based, not content-probed.
- Bidirectional parse transport (`ch parse`, `commands/parse.py`, `xmlmd.py`, `xml_transport.py`): a provider-free boundary that reconstructs `Message` objects from structured JSON or canonical XML-tagged Markdown, then feeds the opposite existing formatter without session discovery or provider parsing.

## Architecture Diagram (Space)

> Focus: The "City Map". Structural boundaries, where things "live", high-level grouping, and external relationships.
> Answers: What are the major building blocks of the system?

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  EXTERNAL WORLD                                                             │
│                                                                             │
│  ┌────────┐      ┌─────────────────────────────────┐      ┌──────────────┐  │
│  │  USER  │─────►│  CLI (ch <subcommand> [args])  │◄─────│ stdin / pipe │  │
│  └────────┘      └────────────────┬────────────────┘      └──────────────┘  │
│                                   │                                         │
╞═══════════════════════════════════│═════════════════════════════════════════╡
│  Chats (System Boundary)          │                                         │
│                                   ▼                                         │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      CLI ROUTER (cli.py:main)                        │   │
│  │   argparse, visibility normalization, ConversationFlags builder      │   │
│  └──────────────────────────────────────┬───────────────────────────────┘   │
│                                         │                                   │
│  ┌──────────────────────────────────────▼────────────────────────────────┐  │
│  │                  COMMAND ORCHESTRATION (commands/)                    │  │
│  │ cmd_parse  cmd_parse_json  cmd_search  cmd_name  cmd_rm              │  │
│  │ cmd_catalog                                                          │  │
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
│  │  JSONL session adapters: Claude / PI / Codex / Antigravity             │  │
│  └──────────────┬─────────────────────────────────────────────────────────┘  │
│                 │                                                            │
│  ┌──────────────▼─────────────────────────────────────────────────────────┐  │
│  │       MODEL + TRANSPORT (model.py, formatting.py, xmlmd.py,          │  │
│  │                          xml_transport.py)                            │  │
│  │  Message / structured JSON / canonical XML / reversible encoding     │  │
│  │  (provider parse and both transport directions converge here)         │  │
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

### Feature 1: Parse (`ch [input] [slice ...]`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ch <input> [slice ...] [flags]`     ──► cli.py:main()
│
├───►  main()                   Detects no subcommand keyword              ──► argparse (default parse)
│      argparse                 Parses flags; handles edge cases:          ──► args namespace
│                               negative-index swap, tool/slice
│                               disambiguation, provider-scoped
│                               recent indices, nargs='?' fixups
│
├───►  main()                   _normalize_role_visibility_args(args)      ──► Resolves --only-user,
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
│      │                        │   │       ├── Walks newest-first by JSONL last timestamp
│      │                        │   │       ├── pool_filter.passes_path_for_index() (cwd)
│      │                        │   │       ├── mafter/cafter timestamp probes
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
├───►  cmd_parse                print_metadata() [if plain xml + not file out] ──► stderr (YAML frontmatter)
│
├───►  cmd_parse                Format output:                             ──► formatted string
│      │                        ├── format_to_xml(messages, flags, map)
│      │                        ├── format_to_json(messages, flags, map)
│      │                        └── format_to_raw(messages, flags, map)
│
├───►  cmd_parse                Emit output:
│      │                        ├── output_file.write_text()               ──► File
│      │                        ├── print(formatted)                       ──► stdout (json/raw/no-color)
│      │                        └── render_message_panels()                ──► Rich console (color)
│      │                            └── [pager if flags.paging]
│
└───►  User                     Sees formatted conversation
```

### Feature 1b: Bidirectional parse transport (`ch parse`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ch parse [-f xml|json] [file]`        ──► cli.py:main()
│                               (file omitted → stdin)
│
├───►  main()                   Detects explicit `parse` subcommand        ──► argparse
│      main()                   cmd_parse_json(input_file, output_format)  ──► commands/parse.py
│
├───►  cmd_parse_json           [xml output] json.loads +                  ──► list[Message]
│                               messages_from_json_data()
│                               OR
│      cmd_parse_json           [json output] messages_from_xmlmd()        ──► list[Message]
│                               Canonical outer/inner blocks and tool
│                               schemas are validated and reconstructed
│
├───►  cmd_parse_json           _build_tool_id_map(messages)               ──► {tool_id: tool_name}
│      cmd_parse_json           format_to_xml() or format_to_json()        ──► opposite representation
│
└───►  cmd_parse_json           Write conversation body only               ──► stdout

This route does not enter `SessionPool`, provider adapters, agent discovery, visibility filtering, shortening, or metadata/frontmatter output. XML-to-JSON canonicalizes only what XML represents: minute-precision dates, shortened IDs, string attributes, schema-visible tool inputs, and rendered-string tool outputs. Both compositions are byte-stable after that canonicalization.
```

### Feature 2: Search (`ch search <pattern>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ch search <pattern> [flags]`        ──► cli.py:main()
│
├───►  main()                   Detects sys.argv[1] == "search"            ──► argparse (search parser)
│      argparse                 Parses: pattern, -l, -ll, -d, -ma,        ──► args namespace
│                               -ca, -f, --only-user/assistant, -T, -t,
│                               -a, -A, -s/-i case mode, --short, --color, etc.
│
├───►  main()                   Builds ConversationFlags + PoolFilter      ──► flags, pool_filter
│      main()                   cmd_search(pattern, flags, pool_filter, ...) ──► commands/
│
├───►  cmd_search               parse_search_query(pattern, case_sensitive) ─► SearchQuery tree
│                               Bare case-insensitive and/or/not tokens → boolean tree
│                               (exit 2 on malformed boolean queries);
│                               otherwise one term: case-aware re.compile + re.escape
│                               fallback + optional literal_candidate
│
├───►  cmd_search               SessionPool.discover(include_sidechains=   ──► pool
│                               flags.show_agents)
│      cmd_search               pool_filter.candidate_files(pool)          ──► provider-narrowed files
│
├───►  cmd_search               iter_hits() — lazily, newest-first by stat   ──► yields SearchHit
│      │                        mtime (reversed pool.stat_mtime_sorted):       as each is confirmed
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
│      │                        ├── _load_conversation_metadata(path)
│      │                        └── Build + yield SearchHit
│
├───►  cmd_search               [if --raw] collect all hits, then            ──► single buffered emit
│                               _format_search_hits_to_raw (single-message
│                               special case needs the full set)
│                               OTHERWISE _stream_search_results(iter_hits):
│      │                        spawn StreamingPager (less -r) when color +
│      │                        paging, then per hit as it arrives:
│      │                        ├── _emit(): render via console.capture(),
│      │                        │   write+flush to less (else print direct)
│      │                        ├── _display_hit():
│      │                        │   ├── [--only-id]: print session ID only
│      │                        │   ├── [--list+color]: stream one row
│      │                        │   ├── [color+matches/full]: per-conversation Panel
│      │                        │   │   (_render_conversation_panel)
│      │                        │   └── else (plain): rule + display_search_result()
│      │                        └── [pager quit early] stop scanning
│
└───►  cmd_search               sys.exit(0 if found_any else 1)
```

### Feature 3: Name (`ch name <id> <name>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ch name <id> <new_name>`            ──► cli.py:main()
│                               or `ch name <id> --auto [-n]`
│
├───►  main()                   Detects sys.argv[1] == "name"              ──► argparse (name parser)
│
├───►  main()                   cmd_name(conversation_id, new_name,        ──► commands/
│                               auto=..., dry_run=...)
│
├───►  cmd_name                 resolve_conversation_file(conv_id)         ──► Path (or exit)
│      │                        └── _try_resolve_conversation_file()
│
├───►  cmd_name                 get_native_session_id(conv_file)           ──► session_id string
│      cmd_name                 get_jsonl_session_adapter(conv_file)       ──► provider adapter
│
├───►  cmd_name                 extract_cwd_from_jsonl(content)            ──► project path | None
│      cmd_name                 decode_jsonl_entries(content)              ──► parsed entries
│
├───►  cmd_name                 [if --auto] _generate_auto_name(...)       ──► pi CLI subprocess
│
├───►  cmd_name                 [if --dry-run] print resolved/generated    ──► stdout
│      │                        name and exit without writes
│
├───►  cmd_name                 adapter.build_name_entries(...)            ──► provider-native rename records
│      │                        ├── Claude: custom-title + agent-name
│      │                        ├── Codex: event_msg(thread_name_updated)
│      │                        └── PI: session_info(name)
│
├───►  cmd_name                 Append provider-native entries to conv_file ─► .jsonl file
│
└───►  cmd_name                 Print confirmation                         ──► console
```

### Feature 4: Remove (`ch rm <session>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ch rm <session> [--dry-run]`        ──► cli.py:main()
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

### Feature 5: Catalog (`ch catalog <args>`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ch catalog <session_ids|greppable>` ──► cli.py:main()
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
Negative index (e.g. -1) ───► │ JSONL recency path    │
                              │  • get_jsonl_last_    │
                              │    timestamp()        │
                              │  • resolve recent     │
                              │    index              │
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
                          name path ─────┼────► append provider-native rename entry/entries
                                         │
                          rm path ───────┼────► collect artifacts + delete
                                         │
                          catalog path ──┴────► cmd_parse capture -> pi CLI

Structured ch JSON ───────────────────► messages_from_json_data()
                                                │
                                                ├── strict schema validation
                                                ├── tool-id map
                                                └── format_to_xml() ──► stdout body

The structured JSON branch bypasses inventory, resolution, format detection, provider adapters, and session metadata.
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
                        │ index (-N)?     │        → walk newest-first by JSONL mtime
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

### Bidirectional Parse Transport State Machine

```
                         ┌────────────────────┐      ┌────────────────────┐
  JSON or XML ──────────►│ DECODE & VALIDATE  │─────►│ RECONSTRUCT        │
                         │ selected grammar /  │      │ Message objects    │
                         │ blocks / tools      │      └─────────┬──────────┘
                         └─────────┬──────────┘                │
                                   │ malformed                  ▼
                                   └──────────► clear error   ┌────────────────────┐
                                                           │ MAP TOOLS & FORMAT │
                                                           │ opposite transport │
                                                           └─────────┬──────────┘
                                                                     ▼
                                                               stdout body only
```

### Search Feature State Machine

```
         ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
  args───►│ PARSE        │─────►│ BUILD        │─────►│ ITERATE      │
         │ SearchQuery  │      │ SessionPool  │      │ search_files │
         │ (terms +     │      │ + provider   │      └──────┬───────┘
         │ and/or tree) │      │ routing      │             │
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
                                                     │ yield SearchHit   │
                                                     └──────┬────────────┘
                                                            │ (raw: collect all, buffer)
                                                     ┌──────▼────────────┐
                                                     │ STREAM hit now:   │
                                                     │ render → less -r  │
                                                     │ (or stdout) as it │
                                                     │ arrives, in scan  │
                                                     │ order (no re-sort)│
                                                     └──────┬────────────┘
                                                            │ pager quit? ──► stop scanning
                                                            ▼
                                              none found ──► exit(1) else exit(0)
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
│   ├── "parse"  → argparse → cmd_parse_json()
│   ├── "search" → argparse → cmd_search()
│   ├── "name"   → argparse → cmd_name()
│   ├── "rm"     → argparse → cmd_rm()
│   ├── "catalog"→ cmd_catalog(argv[2:])
│   └── default  → argparse → cmd_parse()
│
├── [bidirectional parse transport]
│   └── cmd_parse_json(input_file, output_format)
│       JSON → messages_from_json_data() → format_to_xml()
│       OR XML → messages_from_xmlmd() → format_to_json()
│       → stdout body (no resolution/provider/metadata path)
│
├── [default parse mode]
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
│       1. Compile regex in the selected case mode, derive a matching literal candidate
│       2. SessionPool.discover() → candidate files (newest-first by stat mtime)
│       3. Per-file: candidate prefilter → SessionScan → regex confirm → yield SearchHit
│       4. Stream each hit as it is confirmed (no global re-sort); page colored
│          output through a StreamingPager (less -r) writing+flushing per hit
│       5. raw mode is the exception: collect all, then one buffered emit
│
├── [name mode]
│   └── cmd_name(session_id, name, auto=?, dry_run=?)
│       resolve → optional auto-name generation → optional dry-run print
│       → adapter.build_name_entries() → append to file
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
│   ├── search.py     → model, parsing, formatting, session_scan, search_query, console
│   ├── name.py       → model, parsing, formatting, console
│   ├── resolve.py    → model, parsing, session_pool, ordering, utils
│   ├── rm.py         → model, parsing, console, utils
│   └── common.py     → model
├── catalog/          → commands, console, model
├── formatting.py     → model, parsing, console, tools, utils, xml_transport
├── parsing.py        → model, utils
├── tools.py          → parts, registry, utils, xml_transport
├── xmlmd.py          → model, registry, xml_transport
├── xml_transport.py  → registry
├── search_query.py
├── session_pool.py   → model, parsing
├── session_scan.py   → model, parsing, ordering, pool_filter
├── tool_filter.py
├── pool_filter.py    → model, parsing
├── console.py
├── model.py          → utils
├── ordering.py
├── lexer.py          (XmlmdLexer — rendering grammar)
├── parts.py          (MessagePart, MessagePartKind, ToolParts — structured message parts)
├── registry.py       (ContentBlockType, ToolSchema, normalize_tool_name — blocks + tool normalization)
└── theme.py          (Rich theme definitions)
```

---

## Architecture Notes & Edge Cases (Shared Invariants / Non-obvious Behaviors)

1. **Adapter Selection Is Path-Based**: `parse_jsonl_entries()` chooses the provider adapter from `source_path`, not by probing payload shape. Raw stdin JSONL with no source path falls through to the default adapter.
2. **`SessionPool` Owns Inventory, Not Full Truth**: `SessionPool` is the unified inventory/routing layer for exact-id resolution and provider-aware search. It does not currently replace every metadata-heavy path.
3. **Recent Negative Indices Use JSONL Mtime With Cheap Predicates**: `_resolve_recent_conversation_file()` excludes sidechains, applies the cwd probe before timestamp sorting, then orders survivors newest-first by `get_jsonl_last_timestamp()`. Date filters reuse that modified-time value for `mafter` and probe first timestamp only when `cafter` is active. This keeps recent-index resolution tied to transcript content while still avoiding full metadata construction for the pool; sessions without a readable in-band timestamp use the existing filesystem-mtime fallback.
4. **Parse Resolves Input Once**: `_resolve_input_content()` returns `(content, source_path)` so parse mode does not perform a second full resolution pass after reading stdin/path input.
5. **Search Semantics Are Visibility-Dependent**: `cmd_search` matches summaries, the current latest custom title, and the semantic inner XML of visible message content before transport-only escaping. If tools, thinking, agents, plans, or regular user/assistant roles are hidden by flags, they do not count as message matches. Summary and current-title facets intentionally stay outside role selection.
6. **`--agents` Changes the Search Universe**: search does not merely render more content when `-a/--agents` is enabled. It includes Claude sidechain sessions in the `SessionPool` and exposes inline Pi agent records within each Pi session.
7. **Candidate Pass Is an Optimization, Not New Semantics**: plain-literal queries first go through `_search_candidate_matches()`, but every surviving file still gets the normal rendered-content confirmation pass. Render-dependent patterns bypass the candidate shortcut entirely.
8. **Search Metadata Is Lazy**: `_load_conversation_metadata()` is paid only after a file has a content hit. Date filters still apply, but only to candidate hits rather than the entire search universe up front.
9. **Search Output Mode Separates Match Semantics From Display Breadth**: `SessionScan` and regex confirmation always determine the matching conversation first. `SearchOutputMode.MATCHES` renders only `hit.matches` (the default), while `SearchOutputMode.FULL` renders `hit.messages`, including summary/current-title-only hits.
10. **Search Raw Output Is Formatting-Only**: `search -r/--raw` does not change match semantics or breadth semantics. It reuses the same `SearchOutputMode` decision, then formats the chosen messages as plain markdown instead of Rich/XML.
11. **Optional Metadata Stays Sparse**: provider-owned metadata extractors may populate optional fields like `forked_from`, but `print_metadata()` omits absent values instead of rendering null-like placeholders.
12. **Metadata Message Counts After Slicing**: parse-mode metadata reports `len(messages)` after slice application, not the original conversation length.
13. **Tool ID Map Lifecycle**: `_build_tool_id_map()` is deliberately called before parse-mode slicing so that a surviving `tool_result` can still resolve the display name of a sliced-out `tool_use`. Claude `isMeta` text payloads with `sourceToolUseID` are normalized into linked `tool_result` entries, so Skill payloads and similar protocol bodies inherit the same direction/name filtering as ordinary tool outputs.
14. **Agent Merge Heuristics**: `_merge_agent_messages()` performs a timestamp-based merge of Claude sidechains into the main timeline. It infers placement from `Task` dispatch timing rather than a strict relational join.
15. **Catalog API Coupling**: `catalog` captures `cmd_parse()` stdout as an internal API boundary, then shells out to an external `claude` process for summarization.
16. **Shared Session-Title Semantics**: metadata/resolution/search treat provider-native session-name records as one current-title abstraction: Claude `custom-title`, Codex `event_msg.payload.thread_name` when `payload.type == "thread_name_updated"`, and PI `session_info.name`. Only the latest title is acknowledged; historical titles are ignored.
17. **Parse Pool-Filter Scope**: parse-mode `-p/--provider`, `-d/--dir`, `-ma/--mafter`, `-ca/--cafter` narrow only recent negative-index lookup. Exact identifiers, file paths, summary prefixes, and stdin stay unfiltered; the CLI warns when any of these flags would otherwise be ignored. The four flags share a single declarative `PoolFilter` consumed by both `cmd_parse` and `cmd_search`, installed via `add_pool_filter_args`.
18. **Asymmetrical Removal**: `cmd_rm` is Claude-heavy. Native Claude sessions lose sidecar artifacts, history lines, and directories; PI/Codex/Antigravity sessions currently resolve to deleting the single JSONL file.
19. **Antigravity Full Transcript Preference**: Antigravity session discovery treats `{session_id}/.system_generated/logs/transcript_full.jsonl` as canonical when present and falls back to `transcript.jsonl` only for sessions without the full variant. The brain directory name is the native session id.
20. **Boolean Search Is Session-Scoped**: `parse_search_query` interprets bare `and`/`or`/`not` word tokens case-insensitively as a boolean query tree (`and`/`or` with parens; `and` binds tighter). `not` is a separate flat form (`term NOT term [NOT term ...]`) that cannot be mixed with `and`/`or` and does not support parentheses. Each positive term is satisfied by a match anywhere in the session's facets (summaries, current title, rendered messages), so `and` terms may match in different messages; displayed matches are the union over positive terms. `not` terms exclude sessions where the negated term matches in any facet. `-s/--case-sensitive` changes every term's matching mode without changing the case-insensitive operator grammar; `-i/--case-insensitive` is the explicit spelling of the default. Patterns without operator tokens — including regex parens and unterminated quotes — keep verbatim single-regex semantics. Malformed boolean queries exit 2. The literal candidate prefilter evaluates the same tree over per-term raw-content plausibility, treating `not` conservatively (never rejects).
21. **Search Displays As It Scans**: `cmd_search` streams each `SearchHit` the instant `iter_hits()` confirms it, in scan order (newest first by filesystem mtime), instead of buffering, re-sorting by in-band mtime, then paging. `_stream_search_results` renders each hit via `get_console().capture()` and feeds the ANSI to a `StreamingPager` (a long-lived `less -r`) that flushes per hit; quitting `less` early sets `pager.closed`, which stops the scan. Display order therefore remains filesystem mtime, not semantic mtime, because streaming search optimizes for sub-second first results; recent-index resolution is separate and now uses JSONL recency (note 3). Two consequences for the colored `-l` view, whose aggregates can't be known mid-stream: the `N sessions · newest first` line is a trailing summary, and per-row provider labels key off whether the candidate pool spans providers rather than the final hit set. `-r/--raw` opts out (collect-all, single buffered emit) because its single-visible-message rule needs the whole set.
22. **Parse Resolution Avoids Work for Obvious Content and ID-Only Output**: `_resolve_input_content()` treats explicit JSONL/raw transcript content as content, not a possible identifier, so stdin and pasted transcripts do not pay global session-pool discovery. A one-line piped id still resolves. `ParseOutputMode.ONLY_ID` uses `_resolve_input_path()` and stops after identity resolution instead of reading and parsing the session body.
23. **Search Has a Conservative Byte Candidate Gate**: `_search_path_candidate_matches()` rejects only safe ASCII literal misses before `read_text`, using exact bytes for case-sensitive terms and lowercase bytes for the default case-insensitive terms; non-ASCII literals, regex-shaped terms, render-generated markers, and any uncertain case fall through. This gate is only a raw plausibility filter: every survivor must still pass `_search_conversation_content()` and its rendered-message visibility semantics.
24. **`search . -ll` Projection Is Deliberately Narrow**: `_can_project_dot_only_id()` is the eligibility boundary for the only projection fast path: exact dot query, `ONLY_ID`, default visibility, no role/extras, no dir/date filters, and non-raw output. `_project_default_dot_match()` is tri-state; branchable Claude transcripts, read errors, or uncertain cases fall back to `SessionScan`. The projection mirrors default-hidden protocol/tool/thinking/task-notification behavior and should not be broadened without equivalence tests against the full search path.
25. **`ch parse` Is a Provider-Free, Post-Visibility Boundary**: default output follows `messages_from_json_data → format_to_xml`; `-f json` follows `messages_from_xmlmd → format_to_json`. Neither performs session lookup, provider parsing, agent discovery, visibility filtering, or shortening. XML-to-JSON preserves all XML-represented semantics but canonicalizes its intentional losses: dates have minute precision, tool IDs remain shortened, attributes are strings, only schema-visible tool input fields exist, and tool outputs are rendered strings. After that projection, both command compositions are byte-stable. Canonical XML escapes wrapper attributes on messages with `custom_type` metadata. It applies reversible HTML transport encoding when message text resembles an inner block or a typed-block body contains its closing delimiter.
26. **Pi Custom Messages Normalize Inside the Pi Adapter**: generic `type == "custom"` records use the shared `custom` wrapper only under `--all`; valid `pi-user-agents` and `subagents:record` records become shared agent messages under `--agents`; special `type == "custom"` records that cannot normalize fall back to generic data under `--all`. `subagent-notification`, `display:false`, and `custom_message` records without `display:true` never enter the normalized message list. Successful `pi-user-agents` metadata comes from `details`, while only the native `<response>` body supplies response text. A failure requires `details.ok is False`, takes its task and error from `details`, and marks its synthetic Bash result always visible so `--agents` does not require `--tools`. Search and every formatter reuse the same visible messages without provider-specific rendering branches.
