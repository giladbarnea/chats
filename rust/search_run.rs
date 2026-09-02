//! The `ch search` entry point: assemble the pool, the closures and the sink.
//!
//! Ported from `cmd_search` in `src/chats/commands/search.py`. This is the third
//! arm of the cutover — `Help` prints, `Error` prints and exits 2, and `Run` calls
//! here.
//!
//! It owns no logic of its own. `search::plan` supplies the scan order, the screen
//! and the batch probe; `search_confirm` decides a candidate; `search_output` and
//! the coloured views write it. Everything here is wiring and exit status.

use crate::search::parse::SearchArguments;
use crate::search::plan;
use crate::search_confirm::Confirmation;
use crate::search_engine;
use crate::search_output::{
    BufferingSink, PlainOutput, PlainSink, can_use_json_string_gate, confirmed_from,
    displayed_messages, format_raw, path_candidate_matches,
};
use crate::search_query::{self, Query};
use crate::session_pool::{CANDIDATE_WINDOW, SessionPool};
use std::collections::HashSet;
use std::path::{Path, PathBuf};

/// Run one search. The return value is the process exit status.
pub fn run(arguments: &SearchArguments, home: &Path, width: usize) -> i32 {
    let query = match search_query::parse_search_query(&arguments.pattern, arguments.case_sensitive)
    {
        Ok(query) => query,
        // Only a malformed *boolean* query reaches here. An invalid regex is not an
        // error: `compile_search_term` recompiles the escaped literal, so a bad
        // pattern becomes a literal search.
        Err(error) => {
            print_stderr_wrapped(&error.0, crate::search_views::StderrConsole::Error);
            return 2;
        }
    };

    let pool = SessionPool::discover(home, arguments.flags.show_agents);
    // The candidate list is the provider partition, read from *discovery* rows.
    // An empty one exits 1 **silently**, before any scanning, which is why it is
    // checked here rather than folded into the scan's own no-hits outcome.
    if pool.candidate_files(arguments.pool_filter.provider).is_empty() {
        return 1;
    }
    let scan_order = plan::scan_order(&pool, arguments.pool_filter.provider);

    let pi_files: HashSet<PathBuf> = pool
        .by_provider
        .iter()
        .find(|(provider, _)| *provider == crate::inventory::Provider::Pi)
        .map(|(_, paths)| paths.iter().cloned().collect())
        .unwrap_or_default();

    let confirmation = Confirmation::new(
        &query,
        &arguments.flags,
        arguments.pool_filter.directory.clone(),
        home,
    );
    // Python dispatches here, before any gate is built: the projection is a
    // different scan, not a faster one. See `stream_dot_only_id_projection` — it
    // returns sessions the authoritative path rejects, and that is the product's
    // behaviour rather than a bug to be tidied on the way across.
    if can_project_dot_only_id(&query, arguments) {
        return stream_dot_only_id_projection(&scan_order, &confirmation, home);
    }

    let mut undecidable: Option<String> = None;
    let home_display = home.to_string_lossy().into_owned();

    // Two gates, matching Python's two paths. One eligible term gets the batched
    // JSON-string gate over 256 survivors at a time; everything else gets the
    // per-file gate, one file at a time. Both may only ever *reject* a file that
    // could not have matched — a false negative here costs the user a result they
    // will never know they missed, which is why every uncertain case defers.
    let needle = batch_needle(&query, arguments);
    let batch_size = if needle.is_some() { CANDIDATE_WINDOW } else { 1 };

    let outcome = {
        let mut probe = |paths: &[PathBuf]| match &needle {
            Some(needle) => plan::probe(needle, |path| pi_files.contains(path))(paths),
            None => paths
                .iter()
                .map(|path| {
                    path_candidate_matches(
                        path,
                        &query,
                        &arguments.flags,
                        pi_files.contains(path),
                    )
                })
                .collect(),
        };
        let mut confirm = |path: &Path| {
            confirmed_from(path, confirmation.hit(path), &mut undecidable)
        };
        let mut screen = plan::lazy_screen(&arguments.pool_filter);

        if arguments.raw_output {
            let mut sink = BufferingSink::new();
            // The scan's outcome is deliberately unused here: raw decides its
            // own exit from whether any section survived rendering, which is not
            // the same question as whether any session matched. A hit whose
            // visible messages all render empty is a match that prints nothing.
            let _ = search_engine::stream_search(
                &scan_order,
                &mut sink,
                batch_size,
                &mut screen,
                &mut probe,
                &mut confirm,
            );
            if let Some(message) = &undecidable {
                eprintln!("{message}");
                return 1;
            }
            return finish_raw(sink, arguments);
        }

        // The coloured list is a different sink, not a flag on this one. Python
        // branches the same way: `_display_hit` sends `color && LIST` to the row
        // renderer and everything else to the plain path.
        if arguments.flags.color
            && arguments.output_mode == crate::search::parse::SearchOutputMode::List
        {
            let mut sink = crate::search_views::ColouredListSink::new(
                crate::search_views::ColouredListOutput {
                    home: &home_display,
                    width,
                    metrics: crate::cells::CellMetrics::from_environment(),
                    rendering: crate::color::rendering(&stdout_capabilities(arguments.flags.color)),
                    show_provider: list_show_provider(&pool, arguments.pool_filter.provider),
                    now: crate::clock::resolved_now(),
                    paging: arguments.flags.paging,
                },
            );
            search_engine::stream_search(
                &scan_order,
                &mut sink,
                batch_size,
                &mut screen,
                &mut probe,
                &mut confirm,
            )
        } else if arguments.flags.color
            && matches!(
                arguments.output_mode,
                crate::search::parse::SearchOutputMode::Matches
                    | crate::search::parse::SearchOutputMode::Full
            )
        {
            // Python's third arm: `_display_hit` sends `color && (MATCHES | FULL)`
            // to the conversation panel, after the list arm and before the plain
            // path. The panel sink owns its own pager, as the list sink does.
            let mut sink = crate::search_views::ColouredPanelSink::new(
                crate::search_views::ColouredPanelOutput {
                    home: &home_display,
                    flags: &arguments.flags,
                    width,
                    metrics: crate::cells::CellMetrics::from_environment(),
                    rendering: crate::color::rendering(&stdout_capabilities(arguments.flags.color)),
                    now: crate::clock::resolved_now(),
                    paging: arguments.flags.paging,
                    full: arguments.output_mode
                        == crate::search::parse::SearchOutputMode::Full,
                    emit_metadata: arguments.emit_metadata,
                    highlight: crate::search_views::highlight_regex(&query),
                },
            );
            search_engine::stream_search(
                &scan_order,
                &mut sink,
                batch_size,
                &mut screen,
                &mut probe,
                &mut confirm,
            )
        } else {
            let mut sink = PlainSink::new(PlainOutput {
                mode: crate::search_output::output_mode_of(arguments.output_mode),
                flags: &arguments.flags,
                emit_metadata: arguments.emit_metadata,
                home: &home_display,
                width,
                metrics: crate::cells::CellMetrics::from_environment(),
            });
            search_engine::stream_search(
                &scan_order,
                &mut sink,
                batch_size,
                &mut screen,
                &mut probe,
                &mut confirm,
            )
        }
    };

    // Checked before the outcome is trusted. An undecidable pattern answered
    // "no match" for the session that hit it, so the scan's verdict is not an
    // answer to the user's question.
    if let Some(message) = &undecidable {
        print_stderr_wrapped(message, crate::search_views::StderrConsole::Error);
        return 1;
    }

    if outcome.wants_no_results_hint()
        && let Some(hint) = crate::search::render_no_results_hint(
            &arguments.pattern,
            arguments.pool_filter.is_empty(),
            crate::search_output::output_mode_of(arguments.output_mode),
        )
    {
        emit_hint(&hint);
    }
    outcome.exit_status()
}

/// One line to stderr, folded at the console's width the way Rich folds it.
///
/// **Every stderr line the product writes goes through a Rich `Console.print`** —
/// `print_warning`, `print_error` and `print_hint` each build their own
/// `Console(stderr=True)` — so all of them wrap. A raw `eprint!` agrees with the product
/// at any width wide enough not to fold, which is every width a developer types.
///
/// **At width 0 a Rich console renders nothing**, which is why that is a return rather
/// than a degenerate wrap: Rich stores an explicit `COLUMNS` as `_width` and hands it
/// back untouched, so `COLUMNS=0` is a zero-column console rather than a fallback.
pub fn print_stderr_wrapped(message: &str, console: crate::search_views::StderrConsole) {
    let capabilities = stderr_capabilities();
    // **The width comes from stderr's dumbness, not stdout's.** A Rich console returns
    // 80 columns for a dumb terminal *before* it consults `COLUMNS` at all — and these
    // consoles are built on stderr, so it is stderr's tty-ness that decides. Taking
    // `terminal_width()`'s answer instead wraps a dumb-terminal error at the pty's width
    // where the product wraps at 80. Six of 240 recorded cases, all `TERM=dumb`.
    let width = crate::terminal::terminal_width_for(capabilities.is_dumb);
    if width == 0 {
        return;
    }
    let body = message.strip_suffix('\n').unwrap_or(message);
    eprint!(
        "{}",
        crate::search_views::render_stderr_message(
            body,
            console,
            crate::color::rendering(&capabilities),
            width,
        )
    );
}

/// What Rich would decide about **stderr**, which is not what it decides about stdout.
///
/// **`--color` reaches none of these consoles.** `cli.py` passes the choice to
/// `init_module_console`, which builds the *stdout* console; `print_error`,
/// `print_warning` and `print_hint` each build a bare `Console(stderr=True)`, so their
/// colour follows stderr's own tty-ness alone. `ch search nomatch --color never
/// 2>/dev/tty` is coloured. **Preserved, not repaired** — a port resolving the choice
/// once and applying it to every console is more correct and diverges on every
/// no-results search run in a terminal. Preserve-because-wrong item 10.
///
/// **Measured across all three consoles**, four `--color` settings and five tiers,
/// before this was wired: legacy coloured every one of them and this route coloured
/// none. The recorded answers are `tests/data/stderr-colour/`.
fn stderr_capabilities() -> crate::terminal::TerminalCapabilities {
    crate::terminal::resolve_color(&crate::terminal::AmbientColorInputs {
        colorterm: std::env::var("COLORTERM").ok().as_deref(),
        term: std::env::var("TERM").ok().as_deref(),
        force_color: std::env::var("FORCE_COLOR").ok().as_deref(),
        tty_compatible: std::env::var("TTY_COMPATIBLE").ok().as_deref(),
        no_color: std::env::var("NO_COLOR").ok().as_deref(),
        is_a_tty: std::io::IsTerminal::is_terminal(&std::io::stderr()),
        // `--color` never reaches a stderr console, so nothing forces one.
        forced_terminal: false,
    })
}

/// `print_hint`: the no-results line, wrapped at the console's width.
///
/// **It is a Rich `Console.print`, not a `print`.** Python builds
/// `Console(stderr=True, theme=APP_THEME)` and prints through it, so the message folds
/// at the terminal width like every other Rich-rendered line — and at width 0 a Rich
/// console renders **nothing at all**, which is why the empty case is a `return` rather
/// than a degenerate wrap. `eprint!` of the raw string agreed with the product only at
/// widths wide enough not to fold, which is every width a developer types and not
/// `COLUMNS=40`.
fn emit_hint(hint: &str) {
    print_stderr_wrapped(hint, crate::search_views::StderrConsole::Hint);
}

/// Whether coloured list rows carry a provider column.
///
/// Ported from `_list_show_provider`. **Derived from the candidate pool, never
/// from the hits**, and that is the whole subtlety. Python's own docstring says it
/// is hoisted out of the per-hit loop so rows can stream without collecting every
/// hit first — so computing "does this *result set* span two providers" would both
/// give a different answer and require buffering every hit before the first row,
/// destroying the economy the hoist exists to protect.
///
/// It also cannot be caught downstream: the view fixtures take `show_provider` as
/// an **input**, so they grade the rendering given the flag and never the flag's
/// derivation. Any wrong rule leaves every one of them green.
///
/// With no `-p`, the candidate set is the whole pool, so "the candidates span this
/// provider" reduces to "this provider has any file at all".
fn list_show_provider(pool: &SessionPool, provider: Option<crate::inventory::Provider>) -> bool {
    if provider.is_some() {
        return false;
    }
    pool.by_provider
        .iter()
        .filter(|(_, paths)| !paths.is_empty())
        .count()
        > 1
}

/// Colour capability resolved from **stdout**, which is the surface the rows are
/// written to. stderr resolves separately and belongs to the error consoles.
/// What Rich would decide about stdout, **including `--color always`**.
///
/// `cli.py` computes `color = (value == "always") or (value == "auto" and
/// sys.stdout.isatty())` and passes it to `init_module_console` as `force_color`, which
/// becomes Rich's `force_terminal`. That is exactly `flags.color`, so it is threaded
/// here rather than recomputed.
///
/// **Hard-coding `forced_terminal: false` made `--color always` emit no colour at all**
/// when stdout was not a tty — and it was invisible to every gate, because the coloured
/// gates run under a pty where the tty check happens to agree.
///
/// **The stderr consoles are deliberately not forced.** `print_error`, `print_warning`
/// and `print_hint` each build a bare `Console(stderr=True)`, so their colour follows
/// the tty and ignores `--color` entirely. That is preserve-because-wrong item 10.
pub(crate) fn stdout_capabilities(forced_terminal: bool) -> crate::terminal::TerminalCapabilities {
    let colorterm = std::env::var("COLORTERM").ok();
    let term = std::env::var("TERM").ok();
    let force_color = std::env::var("FORCE_COLOR").ok();
    let tty_compatible = std::env::var("TTY_COMPATIBLE").ok();
    let no_color = std::env::var("NO_COLOR").ok();
    crate::terminal::resolve_color(&crate::terminal::AmbientColorInputs {
        colorterm: colorterm.as_deref(),
        term: term.as_deref(),
        force_color: force_color.as_deref(),
        tty_compatible: tty_compatible.as_deref(),
        no_color: no_color.as_deref(),
        is_a_tty: std::io::IsTerminal::is_terminal(&std::io::stdout()),
        forced_terminal,
    })
}

/// The ASCII literal the batch gate searches for, when one term may use it.
fn batch_needle(query: &Query, arguments: &SearchArguments) -> Option<Vec<u8>> {
    let Query::Term(term) = query else {
        return None;
    };
    if !can_use_json_string_gate(term, &arguments.flags) {
        return None;
    }
    Some(term.literal_candidate.as_deref()?.as_bytes().to_vec())
}

/// `--format raw`, the one mode that could not stream.
///
/// A single session with exactly one visible message prints the bare body. Any
/// other shape gets `Session <id>` headers underlined with `=` and joined by
/// `---`. Whether "exactly one" holds is only knowable after the scan, which is
/// the whole reason this mode buffers.
fn finish_raw(sink: BufferingSink, arguments: &SearchArguments) -> i32 {
    let mut sections: Vec<(String, String)> = Vec::new();
    let mut total_visible = 0usize;

    for hit in &sink.hits {
        let indices = displayed_messages(hit, crate::search_output::output_mode_of(arguments.output_mode));
        if indices.is_empty() {
            continue;
        }
        let tool_id_map = crate::visibility::build_tool_id_map(&hit.messages);
        let visible: Vec<crate::model::Message> = indices
            .iter()
            .map(|index| {
                crate::visibility::visible_message(
                    &hit.messages[*index],
                    &arguments.flags,
                    Some(&tool_id_map),
                    &hit.progressive,
                    *index,
                )
            })
            .collect();
        let body = match format_raw(&visible) {
            Ok(body) => body,
            Err(error) => {
                eprintln!("{error}");
                continue;
            }
        };
        if body.is_empty() {
            continue;
        }
        total_visible += visible.len();
        let session_id = crate::search_output::display_session_id(
            &hit.metadata.path,
            hit.metadata.provider,
            hit.metadata.native_id.as_deref(),
        );
        sections.push((format!("Session {session_id}"), body));
    }

    if sink.hits.is_empty() {
        if let Some(hint) = crate::search::render_no_results_hint(
            &arguments.pattern,
            arguments.pool_filter.is_empty(),
            crate::search_output::output_mode_of(arguments.output_mode),
        ) {
            emit_hint(&hint);
        }
        return 1;
    }

    if sections.is_empty() {
        return 0;
    }
    let output = if sections.len() == 1 && total_visible == 1 {
        sections.into_iter().next().expect("length checked").1
    } else {
        sections
            .into_iter()
            .map(|(label, body)| {
                let underline = "=".repeat(label.chars().count());
                format!("{label}\n{underline}\n\n{body}")
            })
            .collect::<Vec<String>>()
            .join("\n\n---\n\n")
    };
    println!("{output}");
    0
}

// ------------------------------------------------- the `search . -ll` projection

/// What the cheap projection concluded about one file.
enum Projection {
    /// Something default-visible is present. Print the id without confirming.
    Match,
    /// Nothing default-visible anywhere in the file.
    NoMatch,
    /// Cannot decide here; fall through to the authoritative path.
    Unknown,
}

/// Whether the narrow `search . -ll` projection may replace full scanning.
///
/// Ported from `_can_project_dot_only_id`. Every clause narrows the query to the
/// one shape the projection models: the bare `.` pattern, id-only output, default
/// visibility, and no filter that would need the file's content.
fn can_project_dot_only_id(query: &Query, arguments: &SearchArguments) -> bool {
    let Query::Term(term) = query else { return false };
    arguments.output_mode == crate::search::parse::SearchOutputMode::OnlyId
        && !arguments.raw_output
        && term.pattern == "."
        && arguments.flags.message_selection == crate::visibility::MessageSelection::All
        && !arguments.flags.show_thinking
        && !tools_requested(&arguments.flags)
        && !arguments.flags.show_agents
        && !arguments.flags.show_branches
        && !arguments.flags.show_plans
        && !arguments.flags.shorten
        && !arguments.flags.shorten_thinking
        && arguments.pool_filter.modified_after.is_none()
        && arguments.pool_filter.created_after.is_none()
        && arguments.pool_filter.directory.is_none()
}

fn tools_requested(flags: &crate::visibility::ConversationFlags) -> bool {
    match &flags.show_tools {
        crate::tool_filter::ToolVisibility::All(shown) => *shown,
        crate::tool_filter::ToolVisibility::Filters(filters) => !filters.is_empty(),
    }
}

/// Stream ids for the narrow default-visibility `search . -ll` path.
///
/// **This is not an optimisation and porting only the authoritative path is a
/// defect.** Measured on the frozen pool: the projection answers `Match` for a Pi
/// session that `_search_hit_for_file` rejects, and the product prints it, because
/// nothing here consults the full path once `Match` is returned. `ch search . -ll`
/// therefore returns a session `ch search .` does not. Reproduced on
/// `~/.pi/agent/sessions/…/2026-04-15T06-53-08-924Z_9b36c7e5-….jsonl`:
/// projection `MATCH`, authoritative path `no hit`.
///
/// A port that "fixes" that disagreement loses a session the product shows, and it
/// passes every gate on this mission. Reproduce the disagreement.
fn stream_dot_only_id_projection(
    scan_order: &[PathBuf],
    confirmation: &Confirmation<'_>,
    home: &Path,
) -> i32 {
    let mut found = false;
    let mut undecidable: Option<String> = None;
    for path in scan_order {
        let provider = crate::inventory::classify_native_session_path_impl(path, home)
            .map(|provider| crate::search_confirm::ProviderBridge::from(provider).0);
        match project_default_dot_match(path, provider) {
            Projection::Match => {
                print_session_id(path, provider);
                found = true;
            }
            Projection::NoMatch => {}
            Projection::Unknown => match confirmation.hit(path) {
                Ok(Some(hit)) => {
                    print_session_id(&hit.metadata.path, Some(hit.metadata.provider));
                    found = true;
                }
                Ok(None) => {}
                // **Once per candidate file, which is why the width-zero guard is not
                // cosmetic.** At `COLUMNS=0` a bare `eprintln!` of an empty wrap wrote
                // 4,947 newlines against Python's nothing; at `COLUMNS=40` the same
                // command writes a megabyte on the Python route, because the message
                // repeats for every file.
                Err(crate::search_confirm::ConfirmError::File(body)) => print_stderr_wrapped(
                    &format!("Error processing conversation file {}: {body}", path.display()),
                    crate::search_views::StderrConsole::Error,
                ),
                Err(crate::search_confirm::ConfirmError::Undecidable(message)) => {
                    undecidable.get_or_insert(message);
                }
            },
        }
    }
    if let Some(message) = &undecidable {
        print_stderr_wrapped(message, crate::search_views::StderrConsole::Error);
        return 1;
    }
    // Exits 0 or 1 with no hint: the hint is suppressed for id-only output anyway.
    if found { 0 } else { 1 }
}

/// Print one session id, flushed individually.
///
/// The per-line flush is the whole deliverable of a measured scope: the first id
/// of a piped `ch search … -ll` went from 15.995 s to 0.38 s with completion time
/// unchanged, purely because Python was block-buffering short lines into a pipe.
fn print_session_id(path: &Path, provider: Option<crate::session::Provider>) {
    let provider = provider.unwrap_or(crate::session::Provider::Claude);
    let native = native_id_from_first_entry(path, provider);
    let id = crate::search_output::display_session_id(path, provider, native.as_deref());
    let mut stdout = std::io::stdout();
    use std::io::Write;
    let _ = writeln!(stdout, "{id}");
    let _ = stdout.flush();
}

/// The provider's own id, read from the file's first decodable entry.
fn native_id_from_first_entry(
    path: &Path,
    provider: crate::session::Provider,
) -> Option<String> {
    if provider == crate::session::Provider::Claude {
        return None;
    }
    let content = std::fs::read_to_string(path).ok()?;
    let entries = crate::session::decode_entries(&content);
    crate::search_confirm::native_session_id(provider, entries.first(), path)
}

/// Whether any entry in the file contributes to default visible search for `.`.
///
/// Streams and stops at the first hit, as Python does. A Claude file always defers:
/// its default visibility depends on branch resolution the projection does not
/// model.
fn project_default_dot_match(
    path: &Path,
    provider: Option<crate::session::Provider>,
) -> Projection {
    // An unclassifiable path defers rather than guessing. Python raises here, but
    // every discovered file sits under a provider root, so the arm is unreachable.
    let Some(provider) = provider else { return Projection::Unknown };
    if provider == crate::session::Provider::Claude {
        return Projection::Unknown;
    }
    let Ok(content) = std::fs::read_to_string(path) else {
        return Projection::Unknown;
    };
    for line in content.split('\n') {
        let stripped = crate::session::python_strip(line);
        if stripped.is_empty() || !stripped.starts_with('{') {
            continue;
        }
        let Ok(serde_json::Value::Object(entry)) = serde_json::from_str(stripped) else {
            continue;
        };
        if entry_has_default_visible_search_facet(&entry, provider) {
            return Projection::Match;
        }
    }
    Projection::NoMatch
}

fn entry_has_default_visible_search_facet(
    entry: &serde_json::Map<String, serde_json::Value>,
    provider: crate::session::Provider,
) -> bool {
    use serde_json::Value;
    if entry.get("type").and_then(Value::as_str) == Some("summary") {
        return entry
            .get("summary")
            .and_then(Value::as_str)
            .is_some_and(|summary| !crate::session::python_strip(summary).is_empty());
    }
    if crate::session::custom_title_from_entry(entry).is_some() {
        return true;
    }
    match provider {
        crate::session::Provider::Pi => pi_entry_has_default_visible_text(entry),
        crate::session::Provider::Codex => codex_entry_has_default_visible_text(entry),
        crate::session::Provider::Claude => false,
    }
}

fn pi_entry_has_default_visible_text(
    entry: &serde_json::Map<String, serde_json::Value>,
) -> bool {
    use serde_json::Value;
    if entry.get("type").and_then(Value::as_str) != Some("message") {
        return false;
    }
    let Some(message) = entry.get("message").and_then(Value::as_object) else {
        return false;
    };
    let role = message.get("role").and_then(Value::as_str);
    if !matches!(role, Some("user") | Some("assistant")) {
        return false;
    }
    let blocks = crate::session::extract_text_blocks(
        message.get("content").unwrap_or(&Value::Null),
    );
    let blocks = if role == Some("user") {
        crate::session::filter_hidden_user_text_blocks(blocks)
    } else {
        blocks
    };
    blocks
        .iter()
        .any(|text| !crate::session::python_strip(text).is_empty())
}

fn codex_entry_has_default_visible_text(
    entry: &serde_json::Map<String, serde_json::Value>,
) -> bool {
    use serde_json::Value;
    if entry.get("type").and_then(Value::as_str) != Some("response_item") {
        return false;
    }
    let Some(payload) = entry.get("payload").and_then(Value::as_object) else {
        return false;
    };
    if payload.get("type").and_then(Value::as_str) != Some("message") {
        return false;
    }
    let content = payload.get("content").unwrap_or(&Value::Null);
    match payload.get("role").and_then(Value::as_str) {
        Some("user") => crate::session::filter_hidden_user_text_blocks(
            crate::session::codex_text_blocks(content),
        )
        .iter()
        .any(|text| {
            !crate::session::python_strip(text).is_empty()
                && !crate::codex::is_preamble_text(text)
        }),
        Some("assistant") => crate::session::codex_text_blocks(content)
            .iter()
            .any(|text| !crate::session::python_strip(text).is_empty()),
        _ => false,
    }
}
