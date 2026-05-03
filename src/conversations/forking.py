from __future__ import annotations

import copy
import json
import time
import uuid
from pathlib import Path

from .model import ConversationFlags
from .parsing import (
    _is_codex_preamble_text,
    _normalize_codex_tool_name,
    _normalize_pi_tool_name,
    get_jsonl_session_adapter,
    get_native_session_id,
)
from .tool_filter import resolve_tool_visibility
from .utils import shorten_data, truncate_middle


def fork_session(source_path: Path, flags: ConversationFlags) -> Path:
    """Fork a supported JSONL session into a thinner resumable copy."""
    adapter_name = get_jsonl_session_adapter(source_path).name
    if adapter_name == "pi":
        return _fork_pi_session(source_path, flags)
    if adapter_name == "codex":
        return _fork_codex_session(source_path, flags)
    return _fork_claude_session(source_path, flags)


def _generate_claude_session_id() -> str:
    return str(uuid.uuid4())


def _generate_claude_agent_id() -> str:
    return uuid.uuid4().hex[:8]


def _generate_pi_session_id() -> str:
    return str(uuid.uuid4())


def _generate_codex_session_id() -> str:
    return str(uuid.uuid7())


def _read_jsonl_entries(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_jsonl_entries(path: Path, entries: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries),
        encoding="utf-8",
    )


def _generate_unique_session_target(
    source_path: Path,
    source_session_id: str,
    generate_session_id,
    build_target_path,
) -> tuple[str, Path]:
    for _ in range(100):
        new_session_id = generate_session_id()
        target_path = build_target_path(source_path, source_session_id, new_session_id)
        if (
            new_session_id != source_session_id
            and target_path != source_path
            and not target_path.exists()
        ):
            return new_session_id, target_path
    raise RuntimeError(f"Unable to generate a unique fork target for {source_path}")


def _generate_unique_agent_target(directory: Path) -> tuple[str, Path]:
    for _ in range(100):
        new_agent_id = _generate_claude_agent_id()
        target_path = directory / f"agent-{new_agent_id}.jsonl"
        if not target_path.exists():
            return new_agent_id, target_path
    raise RuntimeError(
        f"Unable to generate a unique Claude sidechain id in {directory}"
    )


def _replace_stem_suffix(
    source_path: Path,
    source_session_id: str,
    new_session_id: str,
    separator: str,
) -> Path:
    stem = source_path.stem
    if source_session_id and stem.endswith(source_session_id):
        new_stem = stem[: -len(source_session_id)] + new_session_id
    else:
        prefix, sep, _suffix = stem.rpartition(separator)
        new_stem = (
            f"{prefix}{sep}{new_session_id}" if prefix and sep else new_session_id
        )
    return source_path.with_name(f"{new_stem}{source_path.suffix}")


def _build_claude_tool_name_map(entries: list[dict]) -> dict[str, str]:
    id_map: dict[str, str] = {}
    for entry in entries:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content", [])
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "tool_use":
                continue
            tool_id = item.get("id")
            tool_name = item.get("name")
            if isinstance(tool_id, str) and isinstance(tool_name, str):
                id_map[tool_id] = tool_name
    return id_map


def _build_pi_tool_name_map(entries: list[dict]) -> dict[str, str]:
    id_map: dict[str, str] = {}
    for entry in entries:
        if entry.get("type") != "message":
            continue
        message = entry.get("message", {})
        if message.get("role") != "assistant":
            continue
        content = message.get("content", [])
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "toolCall":
                continue
            tool_id = item.get("id")
            tool_name = _normalize_pi_tool_name(item.get("name"))
            if isinstance(tool_id, str):
                id_map[tool_id] = tool_name
    return id_map


def _build_codex_tool_name_map(entries: list[dict]) -> dict[str, str]:
    id_map: dict[str, str] = {}
    for entry in entries:
        if entry.get("type") != "response_item":
            continue
        payload = entry.get("payload", {})
        payload_type = payload.get("type")
        if payload_type not in {"function_call", "custom_tool_call"}:
            continue
        call_id = payload.get("call_id")
        tool_name = payload.get("name")
        if isinstance(call_id, str) and isinstance(tool_name, str):
            id_map[call_id] = _normalize_codex_tool_name(tool_name)
    return id_map


def _shorten_tool_payload(tool: dict, should_shorten: bool) -> dict:
    if not should_shorten:
        return copy.deepcopy(tool)

    shortened_tool = copy.deepcopy(tool)
    if shortened_tool.get("type") == "tool_use" and "input" in shortened_tool:
        shortened_tool["input"] = shorten_data(shortened_tool.get("input"))
    elif shortened_tool.get("type") == "tool_result" and "content" in shortened_tool:
        shortened_tool["content"] = shorten_data(shortened_tool.get("content"))
    return shortened_tool


def _filter_claude_assistant_content(
    content: object,
    flags: ConversationFlags,
    id_map: dict[str, str],
    *,
    show_message_text: bool,
) -> list[dict]:
    if not isinstance(content, list):
        return []

    kept_items: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type == "text":
            if show_message_text and item.get("text", "").strip():
                kept_items.append(copy.deepcopy(item))
            continue

        if item_type == "thinking":
            if not (show_message_text and flags.show_thinking):
                continue
            kept_item = copy.deepcopy(item)
            if flags.shorten or flags.shorten_thinking:
                kept_item["thinking"] = truncate_middle(kept_item.get("thinking", ""))
            kept_items.append(kept_item)
            continue

        if item_type != "tool_use":
            continue

        if item.get("name") == "ExitPlanMode":
            if show_message_text and flags.show_plans:
                kept_items.append(copy.deepcopy(item))
            continue

        if item.get("name") == "Task" and flags.show_agents:
            kept_items.append(copy.deepcopy(item))
            continue

        tool_payload = {
            "type": "tool_use",
            "id": item.get("id"),
            "name": item.get("name"),
            "input": item.get("input", {}),
        }
        show_tool, should_shorten = resolve_tool_visibility(
            tool_payload, flags.show_tools, id_map
        )
        if not show_tool:
            continue

        kept_tool = _shorten_tool_payload(tool_payload, should_shorten)
        kept_items.append({
            **copy.deepcopy(item),
            "input": kept_tool.get("input", {}),
        })

    return kept_items


def _filter_claude_user_content(
    content: object,
    flags: ConversationFlags,
    id_map: dict[str, str],
) -> tuple[list[object], list[tuple[dict, bool]]]:
    if isinstance(content, str):
        return ([content] if flags.show_user_messages and content else []), []

    if not isinstance(content, list):
        return [], []

    kept_items: list[object] = []
    kept_tool_results: list[tuple[dict, bool]] = []
    for item in content:
        if not isinstance(item, dict):
            if flags.show_user_messages:
                kept_items.append(copy.deepcopy(item))
            continue

        if item.get("type") != "tool_result":
            if flags.show_user_messages:
                kept_items.append(copy.deepcopy(item))
            continue

        tool_payload = {
            "type": "tool_result",
            "tool_use_id": item.get("tool_use_id"),
            "content": item.get("content", ""),
            "is_error": item.get("is_error", False),
        }

        if flags.show_agents and id_map.get(item.get("tool_use_id")) == "Task":
            kept_item = copy.deepcopy(item)
            kept_items.append(kept_item)
            kept_tool_results.append((kept_item, False))
            continue

        show_tool, should_shorten = resolve_tool_visibility(
            tool_payload, flags.show_tools, id_map
        )
        if not show_tool:
            continue

        kept_tool = _shorten_tool_payload(tool_payload, should_shorten)
        kept_item = copy.deepcopy(item)
        kept_item["content"] = kept_tool.get("content", "")
        kept_items.append(kept_item)
        kept_tool_results.append((kept_item, should_shorten))

    return kept_items, kept_tool_results


def _rewrite_claude_entries(
    entries: list[dict],
    source_session_id: str,
    new_session_id: str,
    flags: ConversationFlags,
    *,
    agent_id_map: dict[str, str] | None = None,
    show_message_text: bool,
) -> list[dict]:
    id_map = _build_claude_tool_name_map(entries)
    rewritten_entries: list[dict] = []

    for original_entry in entries:
        entry = copy.deepcopy(original_entry)
        if entry.get("sessionId") == source_session_id:
            entry["sessionId"] = new_session_id

        entry_type = entry.get("type")
        if entry_type == "assistant":
            content = entry.get("message", {}).get("content", [])
            filtered_content = _filter_claude_assistant_content(
                content,
                flags,
                id_map,
                show_message_text=show_message_text,
            )
            if not filtered_content:
                continue
            entry["message"]["content"] = filtered_content

        elif entry_type == "user":
            content = entry.get("message", {}).get("content", [])
            filtered_content, kept_tool_results = _filter_claude_user_content(
                content, flags, id_map
            )
            if isinstance(content, str):
                if flags.show_user_messages and content:
                    entry["message"]["content"] = content
                elif kept_tool_results:
                    entry["message"]["content"] = [
                        tool_result for tool_result, _short in kept_tool_results
                    ]
                else:
                    continue
            else:
                entry["message"]["content"] = filtered_content

            tool_use_result = entry.get("toolUseResult")
            if not kept_tool_results:
                entry.pop("toolUseResult", None)
            elif isinstance(tool_use_result, dict):
                should_shorten = kept_tool_results[0][1]
                if should_shorten:
                    entry["toolUseResult"] = shorten_data(tool_use_result)
                if agent_id_map and tool_use_result.get("agentId") in agent_id_map:
                    entry["toolUseResult"]["agentId"] = agent_id_map[
                        tool_use_result["agentId"]
                    ]

        if agent_id_map and entry.get("agentId") in agent_id_map:
            entry["agentId"] = agent_id_map[entry["agentId"]]

        rewritten_entries.append(entry)

    return rewritten_entries


def _extract_claude_agent_id(agent_file: Path) -> str:
    entries = _read_jsonl_entries(agent_file)
    if entries:
        agent_id = entries[0].get("agentId")
        if isinstance(agent_id, str) and agent_id:
            return agent_id
    return agent_file.stem.removeprefix("agent-")


def _find_claude_sidechain_files(source_path: Path, session_id: str) -> list[Path]:
    sidechain_files: list[Path] = []
    search_locations: list[Path] = [
        source_path.parent,
        source_path.parent / session_id / "subagents",
    ]
    for search_dir in search_locations:
        for agent_file in search_dir.glob("agent-*.jsonl"):
            entries = _read_jsonl_entries(agent_file)
            if entries and entries[0].get("sessionId") == session_id:
                sidechain_files.append(agent_file)
    return sorted(sidechain_files)


def _append_claude_history_entry(target_path: Path, new_session_id: str) -> None:
    history_file = Path.home() / ".claude" / "history.jsonl"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_entry = {
        "display": "/fork",
        "pastedContents": {},
        "timestamp": int(time.time() * 1000),
        "project": str(target_path.parent),
        "sessionId": new_session_id,
    }
    with open(history_file, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_entry, separators=(",", ":")) + "\n")


def _fork_claude_session(source_path: Path, flags: ConversationFlags) -> Path:
    source_session_id = get_native_session_id(source_path)
    new_session_id, target_path = _generate_unique_session_target(
        source_path,
        source_session_id,
        _generate_claude_session_id,
        lambda path, _old_id, new_id: path.with_name(f"{new_id}{path.suffix}"),
    )

    source_entries = _read_jsonl_entries(source_path)
    sidechain_files = (
        _find_claude_sidechain_files(source_path, source_session_id)
        if flags.show_agents
        else []
    )
    agent_id_map: dict[str, str] = {}
    sidechain_targets: list[tuple[Path, list[dict]]] = []

    for sidechain_file in sidechain_files:
        old_agent_id = _extract_claude_agent_id(sidechain_file)
        new_agent_id, sidechain_target = _generate_unique_agent_target(
            source_path.parent
        )
        agent_id_map[old_agent_id] = new_agent_id
        sidechain_entries = _rewrite_claude_entries(
            _read_jsonl_entries(sidechain_file),
            source_session_id,
            new_session_id,
            flags,
            agent_id_map={old_agent_id: new_agent_id},
            show_message_text=flags.show_agents,
        )
        sidechain_targets.append((sidechain_target, sidechain_entries))

    main_entries = _rewrite_claude_entries(
        source_entries,
        source_session_id,
        new_session_id,
        flags,
        agent_id_map=agent_id_map,
        show_message_text=flags.show_assistant_messages,
    )

    _write_jsonl_entries(target_path, main_entries)
    for sidechain_target, sidechain_entries in sidechain_targets:
        _write_jsonl_entries(sidechain_target, sidechain_entries)

    _append_claude_history_entry(target_path, new_session_id)
    return target_path


def _filter_pi_assistant_content(
    content: object,
    flags: ConversationFlags,
    id_map: dict[str, str],
) -> list[dict]:
    if not isinstance(content, list):
        return []

    kept_items: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue

        item_type = item.get("type")
        if item_type == "text":
            if flags.show_assistant_messages and item.get("text", "").strip():
                kept_items.append(copy.deepcopy(item))
            continue

        if item_type == "thinking":
            if not (flags.show_assistant_messages and flags.show_thinking):
                continue
            kept_item = copy.deepcopy(item)
            if flags.shorten or flags.shorten_thinking:
                kept_item["thinking"] = truncate_middle(kept_item.get("thinking", ""))
            kept_items.append(kept_item)
            continue

        if item_type != "toolCall":
            continue

        tool_payload = {
            "type": "tool_use",
            "id": item.get("id"),
            "name": _normalize_pi_tool_name(item.get("name")),
            "input": item.get("arguments", {}),
        }
        show_tool, should_shorten = resolve_tool_visibility(
            tool_payload, flags.show_tools, id_map
        )
        if not show_tool:
            continue

        kept_item = copy.deepcopy(item)
        if should_shorten:
            kept_item["arguments"] = shorten_data(kept_item.get("arguments", {}))
        kept_items.append(kept_item)

    return kept_items


def _rewrite_pi_entries(
    entries: list[dict],
    source_session_id: str,
    new_session_id: str,
    flags: ConversationFlags,
) -> list[dict]:
    id_map = _build_pi_tool_name_map(entries)
    rewritten_entries: list[dict] = []

    for original_entry in entries:
        entry = copy.deepcopy(original_entry)
        if entry.get("sessionId") == source_session_id:
            entry["sessionId"] = new_session_id
        if entry.get("parentId") == source_session_id:
            entry["parentId"] = new_session_id

        entry_type = entry.get("type")
        if entry_type == "session":
            entry["id"] = new_session_id
            rewritten_entries.append(entry)
            continue

        if entry_type != "message":
            rewritten_entries.append(entry)
            continue

        message = entry.get("message", {})
        role = message.get("role")
        if role == "user":
            if not flags.show_user_messages:
                continue
            content = message.get("content", [])
            if isinstance(content, list):
                filtered_content = [
                    copy.deepcopy(item)
                    for item in content
                    if isinstance(item, dict) and item.get("text", "").strip()
                ]
                if not filtered_content:
                    continue
                entry["message"]["content"] = filtered_content
            rewritten_entries.append(entry)
            continue

        if role == "assistant":
            filtered_content = _filter_pi_assistant_content(
                message.get("content", []), flags, id_map
            )
            if not filtered_content:
                continue
            entry["message"]["content"] = filtered_content
            rewritten_entries.append(entry)
            continue

        if role != "toolResult":
            continue

        tool_payload = {
            "type": "tool_result",
            "tool_use_id": message.get("toolCallId"),
            "content": message.get("content", []),
            "is_error": message.get("isError", False),
        }
        show_tool, should_shorten = resolve_tool_visibility(
            tool_payload, flags.show_tools, id_map
        )
        if not show_tool:
            continue
        if should_shorten:
            entry["message"]["content"] = shorten_data(message.get("content", []))
        rewritten_entries.append(entry)

    return rewritten_entries


def _fork_pi_session(source_path: Path, flags: ConversationFlags) -> Path:
    source_session_id = get_native_session_id(source_path)
    new_session_id, target_path = _generate_unique_session_target(
        source_path,
        source_session_id,
        _generate_pi_session_id,
        lambda path, old_id, new_id: _replace_stem_suffix(path, old_id, new_id, "_"),
    )

    rewritten_entries = _rewrite_pi_entries(
        _read_jsonl_entries(source_path),
        source_session_id,
        new_session_id,
        flags,
    )
    _write_jsonl_entries(target_path, rewritten_entries)
    return target_path


def _shorten_codex_serialized_value(value: object) -> object:
    if isinstance(value, dict | list):
        return shorten_data(value)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return truncate_middle(value)
            return json.dumps(shorten_data(parsed), separators=(",", ":"))
        return truncate_middle(value)
    return value


def _filter_codex_user_content(content: object) -> list[dict]:
    if not isinstance(content, list):
        return []

    kept_items: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "input_text":
            continue
        text = item.get("text", "")
        if not text.strip() or _is_codex_preamble_text(text):
            continue
        kept_items.append(copy.deepcopy(item))
    return kept_items


def _filter_codex_assistant_content(content: object) -> list[dict]:
    if not isinstance(content, list):
        return []

    kept_items: list[dict] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") != "output_text":
            continue
        if not item.get("text", "").strip():
            continue
        kept_items.append(copy.deepcopy(item))
    return kept_items


def _rewrite_codex_entries(
    entries: list[dict],
    source_session_id: str,
    new_session_id: str,
    flags: ConversationFlags,
) -> list[dict]:
    id_map = _build_codex_tool_name_map(entries)
    rewritten_entries: list[dict] = []

    for original_entry in entries:
        entry = copy.deepcopy(original_entry)
        if entry.get("sessionId") == source_session_id:
            entry["sessionId"] = new_session_id

        entry_type = entry.get("type")
        if entry_type == "session_meta":
            payload = entry.get("payload", {})
            if payload.get("id") == source_session_id:
                payload["id"] = new_session_id
            rewritten_entries.append(entry)
            continue

        if entry_type == "custom-title" or entry_type == "agent-name":
            rewritten_entries.append(entry)
            continue

        if entry_type != "response_item":
            continue

        payload = entry.get("payload", {})
        payload_type = payload.get("type")

        if payload_type == "message":
            role = payload.get("role")
            if role == "user":
                if not flags.show_user_messages:
                    continue
                filtered_content = _filter_codex_user_content(
                    payload.get("content", [])
                )
                if not filtered_content:
                    continue
                payload["content"] = filtered_content
                rewritten_entries.append(entry)
                continue

            if role == "assistant":
                if not flags.show_assistant_messages:
                    continue
                filtered_content = _filter_codex_assistant_content(
                    payload.get("content", [])
                )
                if not filtered_content:
                    continue
                payload["content"] = filtered_content
                rewritten_entries.append(entry)
                continue

            continue

        if payload_type == "reasoning":
            if not flags.show_thinking:
                continue
            summary = payload.get("summary", [])
            if not isinstance(summary, list):
                continue
            filtered_summary: list[dict] = []
            for item in summary:
                if not isinstance(item, dict):
                    continue
                if item.get("type") != "summary_text":
                    continue
                text = item.get("text", "").strip()
                if not text:
                    continue
                kept_item = copy.deepcopy(item)
                if flags.shorten or flags.shorten_thinking:
                    kept_item["text"] = truncate_middle(text)
                filtered_summary.append(kept_item)
            if not filtered_summary:
                continue
            payload["summary"] = filtered_summary
            payload.pop("content", None)
            payload.pop("encrypted_content", None)
            rewritten_entries.append(entry)
            continue

        if payload_type in {"function_call", "custom_tool_call"}:
            tool_payload = {
                "type": "tool_use",
                "id": payload.get("call_id"),
                "name": _normalize_codex_tool_name(payload.get("name")),
                "input": payload.get("arguments")
                if payload_type == "function_call"
                else payload.get("input"),
            }
            show_tool, should_shorten = resolve_tool_visibility(
                tool_payload, flags.show_tools, id_map
            )
            if not show_tool:
                continue
            if should_shorten:
                field_name = "arguments" if payload_type == "function_call" else "input"
                payload[field_name] = _shorten_codex_serialized_value(
                    payload.get(field_name)
                )
            rewritten_entries.append(entry)
            continue

        if payload_type in {"function_call_output", "custom_tool_call_output"}:
            tool_payload = {
                "type": "tool_result",
                "tool_use_id": payload.get("call_id"),
                "content": payload.get("output", ""),
                "is_error": False,
            }
            show_tool, should_shorten = resolve_tool_visibility(
                tool_payload, flags.show_tools, id_map
            )
            if not show_tool:
                continue
            if should_shorten:
                payload["output"] = _shorten_codex_serialized_value(
                    payload.get("output")
                )
            rewritten_entries.append(entry)

    return rewritten_entries


def _fork_codex_session(source_path: Path, flags: ConversationFlags) -> Path:
    source_session_id = get_native_session_id(source_path)
    new_session_id, target_path = _generate_unique_session_target(
        source_path,
        source_session_id,
        _generate_codex_session_id,
        lambda path, old_id, new_id: _replace_stem_suffix(path, old_id, new_id, "-"),
    )

    rewritten_entries = _rewrite_codex_entries(
        _read_jsonl_entries(source_path),
        source_session_id,
        new_session_id,
        flags,
    )
    _write_jsonl_entries(target_path, rewritten_entries)
    return target_path
