---
name: Pi joined user-agent default visibility
updated: 2026-08-09
---
# Joined Pi user-agent messages enter default output

Pi now marks user-agent messages sent into the main context with `details.mainContextState: joined`.
These records still use `display: false`, so `display` does not describe transcript visibility for this custom type.

The Pi adapter now includes only joined `pi-user-agents` `custom_message` records in default output.
The behavior does not require `--agents` or `--tools`.
Non-joined records remain hidden, regardless of their `display` value.
The existing normalization and output formatting remain unchanged.

The implementation lives in `src/chats/parsing.py`.
Behavioral coverage lives in `tests/test_pi_custom_messages.py`.
The historical fixture predates `mainContextState`, so test setup maps its old visible records to the current joined shape.
The complete test suite passed with 934 tests and 3 skips.
A current native Pi session also confirmed that joined entry `62f0ed40` appears in default structured output.

## Accepted product uncertainty

`--agents` also includes `pi-user-agents` `custom` records.
A joined `custom_message` can describe essentially the same background agent payload as a `custom` record.
Therefore, `ch ... --agents` can display both payloads as duplicates.
The user accepted this duplication to ship the default joined-message behavior quickly.
A later design should define stable pairing and deduplication without hiding joined messages from default output.
