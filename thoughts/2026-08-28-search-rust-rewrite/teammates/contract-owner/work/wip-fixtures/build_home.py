#!/usr/bin/env -S uv run
# /// script
# requires-python = "==3.12.*"
# dependencies = []
# ///
"""Build the cycle-03 search-contract characterization home."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOME = Path(sys.argv[1])


def j(obj: object) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=True)


def claude(path: Path, entries: list[dict], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(j(e) + "\n" for e in entries), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def pi(path: Path, entries: list[dict], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(j(e) + "\n" for e in entries), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def codex(path: Path, entries: list[dict], mtime: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(j(e) + "\n" for e in entries), encoding="utf-8")
    os.utime(path, (mtime, mtime))


def user_msg(text: str, ts: str, **extra) -> dict:
    entry = {
        "type": "user",
        "uuid": extra.get("uuid", f"u-{ts}"),
        "timestamp": ts,
        "message": {"role": "user", "content": text},
    }
    if "cwd" in extra:
        entry["cwd"] = extra["cwd"]
    if "sessionid" in extra:
        entry["sessionId"] = extra["sessionid"]
    return entry


def assistant_msg(text: str, ts: str) -> dict:
    return {
        "type": "assistant",
        "uuid": f"a-{ts}",
        "timestamp": ts,
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{"type": "text", "text": text}],
        },
    }


def pi_header(pid: str, cwd: str, ts: str) -> dict:
    return {"type": "session", "version": 3, "id": pid, "timestamp": ts, "cwd": cwd}


def pi_message(role: str, blocks: list[dict], mid: str, ts: str) -> dict:
    return {
        "type": "message",
        "id": mid,
        "parentId": None,
        "timestamp": ts,
        "message": {"role": role, "content": blocks, "timestamp": 1785500000000},
    }


def pi_text(text: str) -> list[dict]:
    return [{"type": "text", "text": text}]


def cx_meta(cid: str, cwd: str, ts: str) -> dict:
    return {
        "timestamp": ts,
        "type": "session_meta",
        "payload": {"id": cid, "cwd": cwd, "thread_source": "user"},
    }


def cx_message(role: str, text: str, ts: str) -> dict:
    return {
        "timestamp": ts,
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": role,
            "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}],
        },
    }


CWD = "/tmp/search-contract"

# ---------------------------------------------------------------- claude alpha
claude(
    HOME / ".claude/projects/alpha/11111111-1111-4111-8111-111111111111.jsonl",
    [
        {"type": "summary", "summary": "Alpha summary needle three", "leafUuid": "leaf-a"},
        user_msg("Alpha needle one body\ndon't panic here", "2026-08-20T10:00:00Z", cwd=CWD + "/alpha"),
        assistant_msg("Beta response about needle two", "2026-08-20T10:01:00Z"),
        {"type": "custom-title", "customTitle": "Alpha Title", "sessionId": "11111111-1111-4111-8111-111111111111"},
    ],
    mtime=1_800_000_100,
)

# ---------------------------------------------------------------- claude bool
claude(
    HOME / ".claude/projects/bool/22222222-2222-4222-8222-222222222222.jsonl",
    [
        user_msg("red fox running", "2026-08-20T11:00:00Z", cwd=CWD + "/bool"),
        assistant_msg("quick dog resting", "2026-08-20T11:01:00Z"),
    ],
    mtime=1_800_000_200,
)

# ---------------------------------------------------------------- claude regex
REGEX_BODY = (
    "start MIDDLE end\n"
    "line2 foo123 bar\n"
    "CAPITAL letters here\n"
    "echo echo again\n"
    "a-b hyphenated\n"
    "one\n"
    "two\n"
    "three\n"
    "trailing tab	end\n"
    "café unicode line\n"
)
claude(
    HOME / ".claude/projects/regex/33333333-3333-4333-8333-333333333333.jsonl",
    [
        user_msg(REGEX_BODY, "2026-08-20T12:00:00Z", cwd=CWD + "/regex"),
        assistant_msg("second block\nwith lines\nfor anchors too", "2026-08-20T12:01:00Z"),
    ],
    mtime=1_800_000_300,
)

# --------------------------------------------------- claude invalid-regex text
INVALID_BODY = (
    "literal patterns below:\n"
    "(?<x>a)\n"
    "\\p{L}\n"
    "\\z anchor\n"
    "[[:alpha:]] class\n"
    "a{,5} interval\n"
    "star* asterisk\n"
    "double** star\n"
    "\\N{GREEK SMALL LETTER ALPHA} named α target\n"
    "\\x{41} braced hex\n"
    "back\\slash single\n"
    "open( paren\n"
    "bracket[mismatch\n"
    "plus+ plus\n"
    "[z-a] range\n"
    "a{2,1} inverted\n"
    "\\8 digit ref\n"
    "(?P=name) group ref\n"
    "(?(1)x|y) conditional\n"
    "\\y bad escape\n"
)
claude(
    HOME / ".claude/projects/invalid/44444444-4444-4444-8444-444444444444.jsonl",
    [user_msg(INVALID_BODY, "2026-08-20T13:00:00Z", cwd=CWD + "/invalid")],
    mtime=1_800_000_400,
)

# ---------------------------------------------------------------- claude case
claude(
    HOME / ".claude/projects/case/55555555-5555-4555-8555-555555555555.jsonl",
    [
        user_msg(
            "Needle case one\nſteady long s\nİstanbul dotted\nkelvin K sign\n",
            "2026-08-20T14:00:00Z",
            cwd=CWD + "/case",
        ),
    ],
    mtime=1_800_000_500,
)

# ---------------------------------------------------------------- claude vis
claude(
    HOME / ".claude/projects/vis/66666666-6666-4666-8666-666666666666.jsonl",
    [
        user_msg("visible opener", "2026-08-20T15:00:00Z", cwd=CWD + "/vis"),
        {
            "type": "assistant",
            "uuid": "a-tools",
            "timestamp": "2026-08-20T15:01:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_v1",
                    "name": "Bash",
                    "input": {"command": "echo visbashcommand"},
                }],
            },
        },
        {
            "type": "user",
            "uuid": "u-toolresult",
            "timestamp": "2026-08-20T15:02:00Z",
            "message": {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_v1",
                    "content": "vistooloutput result text",
                }],
            },
        },
        {
            "type": "assistant",
            "uuid": "a-think",
            "timestamp": "2026-08-20T15:03:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [
                    {"type": "thinking", "thinking": "vishushhush secret thought"},
                    {"type": "text", "text": "visible answer"},
                ],
            },
        },
        {
            "type": "assistant",
            "uuid": "a-plan",
            "timestamp": "2026-08-20T15:04:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_v2",
                    "name": "ExitPlanMode",
                    "input": {"plan": "visplansteps content"},
                }],
            },
        },
    ],
    mtime=1_800_000_600,
)

# branch fixture: two competing roots; last-prompt leaf marks the kept chain
BRANCH_ID = "34343434-3434-4343-8434-343434343434"
claude(
    HOME / f".claude/projects/branches/{BRANCH_ID}.jsonl",
    [
        {"type": "summary", "summary": "Branch session summary", "leafUuid": "leaf-b1"},
        {"type": "user", "uuid": "br-u1a", "parentUuid": None,
         "timestamp": "2026-08-20T16:00:00Z", "cwd": CWD + "/branches",
         "sessionId": BRANCH_ID,
         "message": {"role": "user", "content": "branchabandoned first attempt"}},
        {"type": "assistant", "uuid": "br-a1a", "parentUuid": "br-u1a",
         "timestamp": "2026-08-20T16:00:10Z", "sessionId": BRANCH_ID,
         "message": {"role": "assistant", "model": "claude-sonnet-4-6",
                     "content": [{"type": "text", "text": "branchgone assistant reply"}]}},
        {"type": "user", "uuid": "br-u1b", "parentUuid": None,
         "timestamp": "2026-08-20T16:05:00Z", "cwd": CWD + "/branches",
         "sessionId": BRANCH_ID,
         "message": {"role": "user", "content": "branchkept real attempt"}},
        {"type": "assistant", "uuid": "br-a1b", "parentUuid": "br-u1b",
         "timestamp": "2026-08-20T16:05:10Z", "sessionId": BRANCH_ID,
         "message": {"role": "assistant", "model": "claude-sonnet-4-6",
                     "content": [{"type": "text", "text": "branchkept assistant reply"}]}},
        {"type": "last-prompt", "leafUuid": "br-a1b", "sessionId": BRANCH_ID},
    ],
    mtime=1_800_000_700,
)

# sidechain agent file
claude(
    HOME / ".claude/projects/vis/66666666-6666-4666-8666-666666666666/subagents/agent-side.jsonl",
    [user_msg("sidechainagentsecret text", "2026-08-20T15:30:00Z", cwd=CWD + "/vis")],
    mtime=1_800_001_000,
)

# ------------------------------------------------------------- generated marks
claude(
    HOME / ".claude/projects/mark/67676767-6767-4767-8767-676767676767.jsonl",
    [
        user_msg("markbase opener", "2026-08-20T17:00:00Z", cwd=CWD + "/mark"),
        {
            "type": "assistant",
            "uuid": "a-mread",
            "timestamp": "2026-08-20T17:01:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_m1",
                    "name": "Read",
                    "input": {"file_path": "/tmp/example.txt", "offset": 1, "limit": 2},
                }],
            },
        },
        {
            "type": "user",
            "uuid": "u-mread",
            "timestamp": "2026-08-20T17:02:00Z",
            "message": {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_m1",
                    "content": "plain read output without fences",
                }],
            },
        },
        {
            "type": "assistant",
            "uuid": "a-medit",
            "timestamp": "2026-08-20T17:03:00Z",
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-6",
                "content": [{
                    "type": "tool_use",
                    "id": "toolu_m2",
                    "name": "Edit",
                    "input": {"file_path": "/tmp/app.py", "old_string": "value = 'old'", "new_string": "value = 'new'"},
                }],
            },
        },
        {
            "type": "user",
            "uuid": "u-medit",
            "timestamp": "2026-08-20T17:04:00Z",
            "message": {
                "role": "user",
                "content": [{
                    "type": "tool_result",
                    "tool_use_id": "toolu_m2",
                    "content": "applied edit",
                }],
            },
        },
        # hook additional context: synthesized AdditionalContext tool marker
        {
            "type": "attachment",
            "uuid": "att-hook",
            "parentUuid": "u-medit",
            "attachment": {
                "type": "hook_additional_context",
                "content": ["hookcontexttext injected body"],
                "hookName": "UserPromptSubmit",
                "toolUseID": "hook-abc123",
                "hookEvent": "UserPromptSubmit",
            },
            "timestamp": "2026-08-20T17:05:00Z",
        },
    ],
    mtime=1_800_000_800,
)

# --------------------------------------------------------------------- shorten
claude(
    HOME / ".claude/projects/short/68686868-6868-4868-8868-686868686868.jsonl",
    [
        user_msg("X" * 600 + " tailneedle found", "2026-08-20T18:00:00Z", cwd=CWD + "/short"),
    ],
    mtime=1_800_000_900,
)

# ------------------------------------------------------- claude json escapes
claude(
    HOME / ".claude/projects/esc/69696969-6969-4969-8969-696969696969.jsonl",
    [user_msg('say "hi" and back\\slash plus\ttab café end', "2026-08-20T19:00:00Z", cwd=CWD + "/esc")],
    mtime=1_800_001_100,
)

# hand-crafted \uXXXX-encoded file: decodes to "uescaped tab content needle"
escaped_text = "uescaped tab content needle"
hand_escaped = json.dumps(
    {
        "type": "user",
        "uuid": "u-uesc",
        "timestamp": "2026-08-20T19:30:00Z",
        "cwd": CWD + "/esc",
        "message": {"role": "user", "content": escaped_text},
    },
    separators=(",", ":"),
    ensure_ascii=True,
)
hand_escaped_bytes = hand_encoded = (
    '{"type":"user","uuid":"u-uesc","timestamp":"2026-08-20T19:30:00Z","cwd":"'
    + CWD
    + '/esc","message":{"role":"user","content":"\\u0075es\\u0063aped tab content needle"}}\n'
)
esc_path = HOME / ".claude/projects/uescape/70707070-7070-4707-8707-707070707077.jsonl"
esc_path.parent.mkdir(parents=True, exist_ok=True)
esc_path.write_text(hand_escaped_bytes, encoding="utf-8")
os.utime(esc_path, (1_800_001_150, 1_800_001_150))

# escaped-slash craft: decodes to "slash a/b end"
slashed = (
    '{"type":"user","uuid":"u-slash","timestamp":"2026-08-20T19:40:00Z","cwd":"'
    + CWD
    + '/esc","message":{"role":"user","content":"slash a\\/b end"}}\n'
)
slash_path = HOME / ".claude/projects/uescape/70707070-7070-4707-8707-707070707078.jsonl"
slash_path.parent.mkdir(parents=True, exist_ok=True)
slash_path.write_text(slashed, encoding="utf-8")
os.utime(slash_path, (1_800_001_160, 1_800_001_160))

# ---------------------------------------------------------------------- pi main
pi(
    HOME / ".pi/agent/sessions/contract/2026-08-20T13-00-00-000Z_77777777-7777-4777-8777-777777777777.jsonl",
    [
        pi_header("77777777-7777-4777-8777-777777777777", CWD + "/pimain", "2026-08-20T09:00:00.000Z"),
        {"type": "session_info", "id": "si1", "parentId": None, "timestamp": "2026-08-20T09:00:01.000Z", "name": "Pi Current Title"},
        pi_message("user", pi_text("Pi needle four body"), "pm1", "2026-08-20T09:01:00.000Z"),
        pi_message("assistant", pi_text("Pi response five"), "pa1", "2026-08-20T09:02:00.000Z"),
    ],
    mtime=1_800_002_000,
)

# pi escapes + evidence
pi(
    HOME / ".pi/agent/sessions/contract/2026-08-20T13-10-00-000Z_78787878-7878-4878-8878-787878787878.jsonl",
    [
        pi_header("78787878-7878-4878-8878-787878787878", CWD + "/piesc", "2026-08-20T09:10:00.000Z"),
        pi_message("user", pi_text("pi evidence mentions pi-user-agents explicitly"), "pe1", "2026-08-20T09:11:00.000Z"),
        pi_message("assistant", pi_text("pi café escaped é letter"), "pe2", "2026-08-20T09:12:00.000Z"),
    ],
    mtime=1_800_002_100,
)

# pi agent records (-a) and arbitrary customs (-A)
pi(
    HOME / ".pi/agent/sessions/contract/2026-08-20T13-20-00-000Z_79797979-7979-4979-8979-797979797979.jsonl",
    [
        pi_header("79797979-7979-4979-8979-797979797979", CWD + "/piagent", "2026-08-20T09:20:00.000Z"),
        pi_message("user", pi_text("pi agent base"), "pg1", "2026-08-20T09:21:00.000Z"),
        {
            "type": "custom",
            "customType": "subagents:record",
            "data": {"id": "agent-rec-1", "type": "explorer",
                     "description": "piagentsubagent task words",
                     "status": "done", "result": "piagentresult body"},
            "id": "pc1",
            "parentId": "pg1",
            "timestamp": "2026-08-20T09:22:00.000Z",
        },
        {
            "type": "custom_message",
            "customType": "pi-user-agents",
            "id": "pc2",
            "parentId": "pg1",
            "timestamp": "2026-08-20T09:23:00.000Z",
            "details": {
                "task": "piuseragent task prompt",
                "ok": True,
                "model": "claude-fable-5",
                "mainContextState": "joined",
            },
            "content": (
                "<user_agent>\n<user_invocation>\n"
                "/agent piuseragent task prompt\n"
                "</user_invocation>\n"
                "<task>\npiuseragent task prompt\n</task>\n"
                "<response>\npiuseragentresponse text\n</response>\n"
                "</user_agent>"
            ),
        },
        {
            "type": "custom",
            "customType": "probe-arbitrary",
            "data": {"label": "piarbitrarycustom marker"},
            "id": "pc3",
            "parentId": "pg1",
            "timestamp": "2026-08-20T09:24:00.000Z",
        },
    ],
    mtime=1_800_002_200,
)

# -------------------------------------------------------------------- codex main
codex(
    HOME / ".codex/sessions/2026/08/20/rollout-2026-08-20T12-00-00-88888888-8888-4888-8888-888888888888.jsonl",
    [
        cx_meta("88888888-8888-4888-8888-888888888888", CWD + "/codexmain", "2026-08-20T08:00:00.000Z"),
        cx_message("user", "Codex needle five body", "2026-08-20T08:01:00.000Z"),
        cx_message("assistant", "Codex reply six", "2026-08-20T08:02:00.000Z"),
        {
            "timestamp": "2026-08-20T08:03:00.000Z",
            "type": "response_item",
            "payload": {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "cxreasoning whisper"}],
            },
        },
    ],
    mtime=1_800_003_000,
)

# codex preamble-only
codex(
    HOME / ".codex/sessions/2026/08/20/rollout-2026-08-20T12-05-00-89898989-8989-4989-8989-898989898989.jsonl",
    [
        cx_meta("89898989-8989-4989-8989-898989898989", CWD + "/codexpreamble", "2026-08-20T08:05:00.000Z"),
        cx_message("user", "# AGENTS.md instructions for /tmp/proj\npreamblesecret noise", "2026-08-20T08:06:00.000Z"),
    ],
    mtime=1_800_003_100,
)

# title-only claude session
claude(
    HOME / ".claude/projects/titleonly/71717171-7171-4717-8717-717171717171.jsonl",
    [
        {"type": "custom-title", "customTitle": "TitleOnlySession name", "sessionId": "71717171-7171-4717-8717-717171717171"},
    ],
    mtime=1_800_004_000,
)

# summary-only claude session
claude(
    HOME / ".claude/projects/sumonly/72727272-7272-4727-8727-727272727272.jsonl",
    [
        {"type": "summary", "summary": "SummaryOnlySession digest", "leafUuid": "leaf-s"},
    ],
    mtime=1_800_004_100,
)

# empty-ish session (only a snapshot entry)
claude(
    HOME / ".claude/projects/empty/73737373-7373-4737-8737-737373737373.jsonl",
    [
        {"type": "file-history-snapshot", "messageId": "m", "snapshot": {}, "isSnapshotUpdate": False},
    ],
    mtime=1_800_004_200,
)

# dir-filter targets
claude(
    HOME / ".claude/projects/dirs/74747474-7474-4747-8747-747474747474.jsonl",
    [user_msg("dirfilter target one", "2026-08-20T20:00:00Z", cwd="/tmp/search-contract/dir-a")],
    mtime=1_800_005_000,
)
claude(
    HOME / ".claude/projects/dirs/75757575-7575-4757-8757-757575757575.jsonl",
    [user_msg("dirfilter target two", "2026-08-20T20:01:00Z", cwd="/tmp/search-contract/dir-b")],
    mtime=1_800_005_100,
)

print(f"built {HOME}")

# long tool output for shorten interaction (appended after first build)
long_tool = HOME / ".claude/projects/shorttool/76767676-7676-4776-8776-767676767676.jsonl"
long_tool.parent.mkdir(parents=True, exist_ok=True)
entries = [
    {
        "type": "assistant",
        "uuid": "a-lt",
        "timestamp": "2026-08-20T21:00:00Z",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-6",
            "content": [{
                "type": "tool_use",
                "id": "toolu_lt",
                "name": "Bash",
                "input": {"command": "echo longtooloutput"},
            }],
        },
    },
    {
        "type": "user",
        "uuid": "u-lt",
        "timestamp": "2026-08-20T21:01:00Z",
        "cwd": CWD + "/shorttool",
        "message": {
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": "toolu_lt",
                "content": "Y" * 40 + " middlenosecret hidden" + "Z" * 40 + " longtooloutput tail",
            }],
        },
    },
]
long_tool.write_text("".join(j(e) + "\n" for e in entries), encoding="utf-8")
os.utime(long_tool, (1_800_005_200, 1_800_005_200))
print("appended shorttool session")

# false-candidate file: raw bytes contain e9 only inside the u00e9 escape
false_cand = (
    '{"type":"user","uuid":"u-fc","timestamp":"2026-08-20T19:50:00Z","cwd":"'
    + CWD
    + '/esc","message":{"role":"user","content":"only \\u00e9 accent here"}}\n'
)
fc_path = HOME / ".claude/projects/uescape/70707070-7070-4707-8707-707070707079.jsonl"
fc_path.parent.mkdir(parents=True, exist_ok=True)
fc_path.write_text(false_cand, encoding="utf-8")
os.utime(fc_path, (1_800_001_170, 1_800_001_170))
print("appended false-candidate session")

# conditional-target line appended to the invalid-regex session
inv_path = HOME / ".claude/projects/invalid/44444444-4444-4444-8444-444444444444.jsonl"
text = inv_path.read_text(encoding="utf-8")
entry = {
    "type": "user",
    "uuid": "u-kettle",
    "timestamp": "2026-08-20T13:10:00Z",
    "cwd": CWD + "/invalid",
    "message": {"role": "user", "content": "kettlexyz conditional target"},
}
inv_path.write_text(text + j(entry) + "\n", encoding="utf-8")
print("appended kettle target")

# greek-alpha target session: contains α WITHOUT the \N{...} escape text,
# so a reject-to-literal engine cannot coincide with regex truth (review F3)
greek_path = HOME / ".claude/projects/greek/7a7a7a7a-7a7a-4a7a-8a7a-7a7a7a7a7a7a.jsonl"
greek_path.parent.mkdir(parents=True, exist_ok=True)
greek_entry = {
    "type": "user",
    "uuid": "u-greek",
    "timestamp": "2026-08-20T22:00:00Z",
    "cwd": CWD + "/greek",
    "message": {"role": "user", "content": "greek alpha \u03b1 here"},
}
greek_path.write_text(j(greek_entry) + "\n", encoding="utf-8")
os.utime(greek_path, (1_800_006_000, 1_800_006_000))
print("appended greek-alpha session")
