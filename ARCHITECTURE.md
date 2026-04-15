---
name: architecture
description: Document the architecture of the `ccc` CLI tool.
last_updated: 2026-04-14, 796506c
---

# ARCHITECTURE.md

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
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │   │
│  │  │ Subcommand   │  │ Flag/Arg     │  │ ConversationF│               │   │
│  │  │ Detector     │──►│ Parser       │──►│ lags Builder │               │   │
│  │  └──────────────┘  └──────────────┘  └──────┬───────┘               │   │
│  └─────────────────────────────────────────────│───────────────────────┘   │
│                                                │                           │
│          ┌─────────────────────────────────────▼────────────────────────┐   │
│          │                     COMMANDS (commands.py)                   │   │
│          │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────┐ ┌────────┐    │   │
│          │  │cmd_parse │ │cmd_search│ │cmd_rename│ │rm  │ │catalog │    │   │
│          │  └─────┬────┘ └────┬─────┘ └────┬─────┘ └─┬──┘ └───┬────┘    │   │
│          └────────│──────────│──────────│──────────│────────│───────────┘   │
│                   │          │          │          │        │               │
│  ┌────────────────▼──────────▼──────────┼──────────┼────────┼────────────┐  │
│  │            SESSION RESOLUTION                   │        │            │  │
│  │  ┌─────────────────────────────────────────┐    │        │            │  │
│  │  │ _try_resolve_conversation_file()        │    │        │            │  │
│  │  │  1. Direct path  2. Negative index      │    │        │            │  │
│  │  │  3. Exact ID/name  4. Summary prefix    │    │        │            │  │
│  │  └─────────────────────────────────────────┘    │        │            │  │
│  └─────────────────────────────────────────────────┼────────┼────────────┘  │
│                   │          │                      │        │               │
│  ┌────────────────▼──────────▼──────────────────────▼────────┼────────────┐  │
│  │               PARSING LAYER (parsing.py)                  │            │  │
│  │  ┌─────────────┐  ┌────────────────────────────────────┐  │            │  │
│  │  │detect_format│  │  JSONL Session Adapters            │  │            │  │
│  │  │ jsonl / raw │  │  ┌─────────┐┌────┐┌───────┐        │  │            │  │
│  │  └─────────────┘  │  │ Default ││ PI ││ Codex │        │  │            │  │
│  │                   │  │(Claude) ││    ││       │        │  │            │  │
│  │                   │  └─────────┘└────┘└───────┘        │  │            │  │
│  │                   └────────────────────────────────────┘  │            │  │
│  └───────────────────────────────────────────────────────────┼────────────┘  │
│                   │          │                                │               │
│  ┌────────────────▼──────────▼────────────────────────────┐   │               │
│  │            MODEL LAYER (model.py, parts.py)            │   │               │
│  │  ┌─────────┐  ┌──────────────────┐  ┌──────────────┐   │   │               │
│  │  │ Message │  │ConversationFlags │  │ MessagePart  │   │   │               │
│  │  │         │──►│iter_visible_parts│──►│ TEXT|THINK|│   │   │               │
│  │  │         │  │                  │  │ TOOL         │   │   │               │
│  │  └─────────┘  └──────────────────┘  └──────────────┘   │   │               │
│  └────────────────────────────────────────────────────────┘   │               │
│                   │          │                                │               │
│  ┌────────────────▼──────────▼────────────────────┐           │               │
│  │         FORMATTING LAYER (formatting.py)       │           │               │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────────┐   │           │               │
│  │  │format_xml│ │format_json│ │format_raw     │   │           │               │
│  │  │          │ │          │ │               │   │           │               │
│  │  └──────────┘ └──────────┘ └───────────────┘   │           │               │
│  │  ┌──────────────────────┐ ┌────────────────┐   │           │               │
│  │  │render_messages_rich  │ │print_metadata  │   │           │               │
│  │  └──────────────────────┘ └────────────────┘   │           │               │
│  └────────────────────────────────────────────────┘           │               │
│                                                               │               │
│  ┌───────────────────────────────────────────────────────────▼────────────┐ │
│  │                    CATALOG MODULE (catalog/)                           │ │
│  │  ┌────────────────┐  ┌──────────────┐  ┌──────────────────────────┐    │ │
│  │  │catalog_sessions│──►│_get_session_ │──►│ subprocess: claude CLI │    │ │
│  │  │                │  │ content()    │  │ (sonnet, -p prompt)      │    │ │
│  │  └────────────────┘  └──────────────┘  └──────────────────────────┘    │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
╞═════════════════════════════════════════════════════════════════════════════╡
│  EXTERNAL                                                                   │
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

### Feature 1: Parse (`ccc [input] [slice]`)

```
TIME   ACTOR                    ACTION                                         TARGET
│
├───►  User                     Runs `ccc <input> [slice] [flags]`         ──► cli.py:main()
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
│      │                        │   ├── is_single_negative_index()
│      │                        │   │   └── _resolve_recent_conversation_file()
│      │                        │   │       ├── find_all_supported_session_files()
│      │                        │   │       ├── _build_conversation_metadata()
│      │                        │   │       └── resolve_negative_index()
│      │                        │   ├── Match by exact filename/native session id
│      │                        │   ├── Match by summary prefix
│      │                        └── Returns file content string + source path
│
├───►  cmd_parse                detect_format(content)                     ──► "jsonl" | "raw"
│
├───►  cmd_parse                parse_jsonl(content, flags, source_path)   ──► parsing.py
│      │                        ├── _select_jsonl_session_adapter()
│      │                        │   (PI path → _parse_pi_jsonl,
│      │                        │    Codex path → _parse_codex_jsonl,
│      │                        │    else → _parse_default_jsonl)
│      │                        └── adapter.parse_messages(content, flags) ──► list[Message]
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
├───►  cmd_parse                parse_slice_notation(slice_str)            ──► (start, stop)
│      cmd_parse                messages = messages[start:stop]
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
│
├───►  cmd_search               find_all_supported_session_files()         ──► list[Path]
│      cmd_search               _build_conversation_metadata(files)        ──► list[ConversationMetadata]
│                               (sorted oldest→newest by mtime)
│
├───►  cmd_search               For each metadata entry:
│      │                        ├── _passes_date_filters(meta, mafter, cafter)
│      │                        └── _search_conversation(path, regex, flags, dir)
│      │                            ├── detect_format(content)
│      │                            ├── parse_jsonl() or parse_raw_cli_transcript()
│      │                            ├── Apply dir_filter (cwd relative_to check)
│      │                            ├── extract_summaries_from_content()
│      │                            ├── extract_custom_titles_from_content()
│      │                            ├── regex.search(summary) for each summary
│      │                            ├── regex.search(title) for each title
│      │                            ├── _build_tool_id_map(messages)
│      │                            └── regex.search(render_message_inner_xml(msg))
│      │                                for each message
│
├───►  cmd_search               display_search_result() for each match:
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
├───►  cmd_rename               get_display_session_id(conv_file)          ──► session_id string
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
[ RAW INPUT ]                [ RESOLUTION ]               [ PARSING ]                [ OUTPUT ]
(ID / Path / stdin)          (File Lookup)                (Format → Messages)        (Display)

                             ┌────────────────┐
Session UUID ──────────────► │ Direct stem    │
                             │ match in       │
                             │ projects/*/    │
                             └───────┬────────┘
                             ┌───────▼────────┐           ┌──────────────────┐
Negative index (e.g. -1) ──► │ Sort all files │           │                  │
                             │ by mtime (asc),│           │ detect_format()  │
                             │ pick Nth from  │──────────►│  ├─ "jsonl"      │
                             │ end            │           │  │  ├─ Claude    │
                             └───────┬────────┘           │  │  ├─ PI        │
                             ┌───────▼────────┐           │  │  └─ Codex     │
Summary prefix ────────────► │ Scan summaries │           │  └─ "raw"        │
                             │ case-insensitive│          │    (CLI xscript) │
                             └───────┬────────┘           └────────┬─────────┘
                                     │                    │  .text           │       ┌──────────────┐
                                     ▼                    │  .thinking       │──────►│ XML format   │
                              .jsonl file content         │  .tools[]        │       ├──────────────┤
                                     │                    │  .plan           │──────►│ JSON format  │
                                     │                    │  .agent_id       │       ├──────────────┤
                                     │                    │  .timestamp      │──────►│ Raw format   │
                                     │                    │  .model          │       ├──────────────┤
                                     │                    └──────────────────┘──────►│ Rich console │
                                     │                           │                  │  (w/ pager)  │
                                     │                           │                  ├──────────────┤
                                     │                    ┌──────▼──────┐            │ File output  │
                                     │                    │ Slice [s:e] │            └──────────────┘
                                     │                    └─────────────┘
                                     │
                                     │                    ┌──────────────────┐
                                     ├───── (search) ────►│ regex.search()   │──► matching messages
                                     │                    │ against rendered  │    + summaries + titles
                                     │                    │ inner XML         │
                                     │                    └──────────────────┘
                                     │
                                     │                    ┌──────────────────┐
                                     ├───── (rename) ────►│ Append JSON      │──► .jsonl file
                                     │                    │ entries to file   │    + history.jsonl
                                     │                    └──────────────────┘
                                     │
                                     │                    ┌──────────────────┐
                                     ├───── (rm) ────────►│ Collect & delete │──► files, dirs,
                                     │                    │ session artifacts │    history entries
                                     │                    └──────────────────┘
                                     │
                                     │                    ┌──────────────────┐
                                     └───── (catalog) ───►│ Render session   │──► subprocess
                                                          │ → build prompt   │    claude CLI
                                                          │ → invoke claude  │──► sessions.yaml
                                                          └──────────────────┘
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
                        ┌──────▼──────────┐  yes
                        │ Is negative     │──────► Sort all sessions by mtime (asc)
                        │ index (-N)?     │        → pick Nth from end
                        └──────┬──────────┘        → RESOLVED (Path) or NOT_FOUND
                               │ no
                        ┌──────▼──────────┐  yes
                        │ Single word?    │──────► Scan the unified session pool for
                        │ Exact ID/name?  │        exact filename/native session id
                        │                 │        → RESOLVED (Path)
                        └──────┬──────────┘          or fall through
                               │ no match
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
         ┌───────────┐      ┌──────────────┐      ┌──────────────┐
  args───►│ COMPILE   │─────►│ DISCOVER     │─────►│ ITERATE      │
         │ regex     │      │ all session  │      │ sessions     │
         │ (or       │      │ files +      │      └──────┬───────┘
         │ escape)   │      │ metadata     │             │
         └───────────┘      └──────────────┘      ┌──────▼───────┐
                                                  │ Per session: │
                                              no  │ date filter? │──► SKIP
                                                  └──────┬───────┘
                                                         │ yes
                                                  ┌──────▼───────┐
                                              no  │ dir filter?  │──► SKIP
                                                  └──────┬───────┘
                                                         │ pass
                                                  ┌──────▼───────┐
                                                  │ Parse +      │
                                                  │ regex search │
                                                  │ messages,    │
                                                  │ summaries,   │
                                                  │ titles       │
                                                  └──────┬───────┘
                                                         │
                                              ┌──────────▼──────────┐
                                              │ Any matches?       │
                                          no  │                    │ yes
                                     SKIP ◄───│                    │───► DISPLAY
                                              └────────────────────┘
                                                                        │
                                              exit(0) if any found ◄────┘
                                              exit(1) if none
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
│   │   ├── is_single_negative_index(identifier)
│   │   │   └── _resolve_recent_conversation_file(identifier, files)
│   │   │       ├── _build_conversation_metadata(files)
│   │   │       │   ├── _load_conversation_metadata(conv_file)
│   │   │       │   │   └── get_jsonl_timestamps(conv_file)
│   │   │       │   │       ├── _find_first_timestamp()
│   │   │       │   │       ├── _find_last_timestamp()
│   │   │       │   │       └── _parse_iso_timestamp()
│   │   │       │   └── _order_metadata_by_modified_time()
│   │   │       │       └── sort_by_modified()
│   │   │       └── resolve_negative_index(identifier, ordered)
│   │   ├── _resolve_exact_session_identifier(identifier, files)
│   │   │   └── get_native_session_id(conv_file)
│   │   ├── extract_summaries_from_jsonl(conv_file) (prefix match)
│   │   │   └── _extract_field_from_jsonl()
│   │   │       └── _extract_field_from_content()
│   └── path.read_text()
│
├── detect_format(content) → "jsonl" | "raw"
│
├── parse_jsonl(content, flags, source_path)
│   ├── _select_jsonl_session_adapter(source_path)
│   │   ├── _is_pi_jsonl_path()
│   │   ├── _is_codex_jsonl_path()
│   │   └── default (always matches)
│   └── adapter.parse_messages(content, flags)
│       ├── _parse_default_jsonl(content, flags)
│       │   ├── _iter_jsonl_entries(content)
│       │   ├── _parse_user_entry(entry, index, flags)
│       │   │   ├── _extract_text_blocks(content_data)
│       │   │   └── shorten_tool_use_id()
│       │   ├── _parse_assistant_entry(entry, index, flags)
│       │   └── _parse_custom_title_entry(entry, index)
│       ├── _parse_pi_jsonl(content, flags)
│       │   ├── _iter_jsonl_entries(content)
│       │   ├── _parse_pi_message_entry(entry, index, flags)
│       │   │   └── _normalize_pi_tool_name()
│       │   └── _parse_custom_title_entry()
│       └── _parse_codex_jsonl(content, flags)
│           ├── _iter_jsonl_entries(content)
│           ├── _extract_codex_text_blocks(content_data)
│           ├── _is_codex_preamble_text()
│           ├── _extract_codex_reasoning_text()
│           ├── _parse_codex_tool_input()
│           ├── _append_codex_block()
│           └── _parse_custom_title_entry()
│
├── parse_raw_cli_transcript(content, flags) [if format == "raw"]
│
├── _merge_agent_messages(messages, content, input_file_path, flags)
│   ├── get_display_session_id(input_file_path)
│   ├── find_agent_files_for_session(input_file_path, session_id)
│   ├── _extract_task_dispatches(content)
│   └── parse_jsonl(agent_content, flags, source_path=agent_file)
│
├── _build_tool_id_map(messages)
├── parse_slice_notation(slice_str)
│   ├── _parse_single_index()
│   └── _convert_slice_bound()
│
├── [metadata]
│   ├── extract_custom_titles_from_content(content)
│   ├── _load_conversation_metadata(input_file_path)
│   └── print_metadata(path, cwd, count, ...)
│       ├── get_display_session_id()
│       └── collapse_home()
│
├── [format output]
│   ├── format_to_xml(messages, flags, tool_id_map)
│   │   └── render_message_inner_xml(msg, flags, tool_id_map)
│   │       ├── msg.iter_visible_parts(flags, tool_id_map)
│   │       │   ├── shorten_data(text) [if flags.shorten]
│   │       │   ├── truncate_middle(thinking) [if shorten]
│   │       │   ├── _append_tool_parts(parts, flags, tool_id_map)
│   │       │   │   ├── _should_show_tool(tool, filter_value, id_map)
│   │       │   │   │   └── ToolFilter._matches_criteria()
│   │       │   │   │       └── _resolve_tool_name()
│   │       │   │   └── tool_to_parts(tool, id_map) → ToolParts
│   │       │   │       ├── _tool_use_to_parts()
│   │       │   │       │   ├── TOOL_SCHEMAS[name]
│   │       │   │       │   ├── _format_edit_content() [if Edit]
│   │       │   │       │   └── shorten_tool_use_id()
│   │       │   │       └── _tool_result_to_parts()
│   │       │   │           └── extract_text_from_content()
│   │       │   └── [plan as ToolParts with name="ExitPlanMode"]
│   │       └── render_tool_xml(parts)
│   │
│   ├── format_to_json(messages, flags, tool_id_map)
│   │   └── render_message_inner_xml() [per message]
│   │
│   └── format_to_raw(messages, flags, tool_id_map)
│       └── render_message_inner_xml() [per message]
│
└── [emit output]
    ├── output_file.write_text()
    ├── print(formatted)
    └── render_messages_with_rich(messages, flags, tool_id_map)
        ├── msg.iter_visible_parts(flags, tool_id_map)
        ├── Markdown(text) or Text(text) [for XML-tagged content]
        ├── render_tool_rich(parts) → [Text | Markdown]
        └── get_console().print()

cmd_search(pattern, flags, list_only, only_id, dir_filter, mafter, cafter)
├── parse_date_filter(mafter) / parse_date_filter(cafter)
├── re.compile(pattern)
├── find_all_supported_session_files()
│   ├── Path.home() / ".claude" / "projects" glob
│   └── JSONL_SESSION_ADAPTERS[*].find_session_files()
│       ├── _find_pi_session_files()
│       └── _find_codex_session_files()
├── _build_conversation_metadata(files)
├── _passes_date_filters(meta, mafter_dt, cafter_dt)
├── _search_conversation(path, regex, flags, dir_filter)
│   ├── detect_format() → parse_jsonl() or parse_raw_cli_transcript()
│   ├── extract_cwd_from_jsonl()
│   │   └── _extract_cwd_from_codex_entry() [for Codex files]
│   ├── extract_summaries_from_content()
│   ├── extract_custom_titles_from_content()
│   ├── _build_tool_id_map()
│   └── render_message_inner_xml() [for regex matching]
└── display_search_result()
    ├── get_display_session_id()
    ├── print_metadata()
    ├── _build_tool_id_map()
    ├── render_messages_with_rich() [if color]
    └── format_to_xml() [if no color]

cmd_rename(conversation_id, new_name)
├── resolve_conversation_file(conversation_id)
│   └── _try_resolve_conversation_file()
├── get_display_session_id()
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
│   ├── console.py          (get_console, print_error)
│   ├── date_filters.py     (parse_date_filter)
│   ├── formatting.py       (format_to_xml/json/raw, print_metadata, render_*)
│   │   ├── console.py
│   │   ├── model.py
│   │   ├── parsing.py      (get_display_session_id)
│   │   ├── parts.py        (MessagePartKind)
│   │   ├── registry.py     (ContentBlockType)
│   │   ├── tools.py        (render_tool_xml, render_tool_rich)
│   │   │   ├── parts.py    (ToolParts)
│   │   │   ├── registry.py (TOOL_SCHEMAS, ContentBlockType)
│   │   │   └── utils.py    (extract_text_from_content, shorten_tool_use_id)
│   │   └── utils.py        (collapse_home)
│   ├── model.py             (ConversationFlags, ConversationMetadata, Message)
│   │   ├── parts.py        (MessagePart, MessagePartKind, ToolParts)
│   │   ├── registry.py     (ContentBlockType)
│   │   ├── tool_filter.py  (ToolFilter)
│   │   ├── tools.py        (tool_to_parts)
│   │   └── utils.py        (shorten_data, truncate_middle)
│   ├── ordering.py          (resolve_negative_index, sort_by_modified, is_single_negative_index)
│   ├── parsing.py           (detect_format, parse_jsonl, parse_raw_cli_transcript, extract_*, ...)
│   │   ├── model.py
│   │   └── utils.py        (shorten_tool_use_id)
│   └── utils.py             (collapse_home)
├── console.py
├── model.py
├── ordering.py
├── tool_filter.py           (ToolFilter, parse_tool_spec)
└── catalog/
    ├── __init__.py          (catalog_sessions)
    │   ├── commands.py      (cmd_parse)
    │   ├── console.py
    │   └── model.py         (ConversationFlags)
    └── assets/
        └── sessions.template.yaml
```

---

## Architecture Notes & Edge Cases (Shared Invariants / Non-obvious Behaviors)

1. **Adapter Selection Sensitivity**: `parse_jsonl` does **not** inspect the structure of the JSONL payload to determine the adapter. It makes the decision based entirely on the `source_path` location (e.g., `~/.pi/...` triggers the PI adapter). Raw stdin JSONL with no source path will fall through to the default adapter.
2. **Search Matches Against Rendered Content**: `cmd_search` matches against the *rendered* XML content (via `render_message_inner_xml()`), meaning results directly vary with visibility flags (e.g., tools or thinking blocks will not be matched unless their visibility flags are enabled). 
3. **Search Universe Mutation**: Adding `--agents` to a search not only changes the output rendering, but also modifies the universe of files searched via `find_all_supported_session_files(include_sidechains=flags.show_agents)`.
4. **Metadata Message Counts After Slicing**: In the Parse flow, the emitted metadata (`messages: {total_messages}`) computes `len(messages)` *after* message slicing. It does not reflect the original un-sliced conversation length.
5. **Tool ID Map Lifecycle**: `_build_tool_id_map` is deliberately called *before* applying slicing bounds in `cmd_parse`. This ensures that even if a `tool_use` input is sliced out, its corresponding `tool_result` can still properly resolve its display name.
6. **Agent Merge Heuristics**: `_merge_agent_messages()` performs a timestamp-based inference to merge sidechain agents into the main timeline, rather than relying on a strict relational join constraint. It traces `Task` dispatch timestamps to interleave blocks chronologically.
7. **Catalog API Coupling**: The `catalog` module relies heavily on parsing `cmd_parse` stdout to capture structured/pre-rendered context, acting essentially as an internal CLI API. Furthermore, the summarization invokes an external process (`subprocess.run(["claude", ...])`) rather than using an in-memory API client.
8. **Asymmetrical Removal**: `cmd_rm` behaves asymmetrically. For native Claude sessions, it deletes sidecar artifacts, debug logs, file history, and rewrites the history JSONL index. For non-Claude resolved sessions (PI/Codex), it simply deletes the single resolved JSONL file.
