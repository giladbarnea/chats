# `conversations` Skill Development

Current code quality issues, known technical debt, development conventions, and future ideas.

---

## Contributors

1. Read in full every source file, recursively, except `tests/data/*` because the files there are huge.
2. If developing or enhancing a feature, iterate with the user which behaviors should be tested by way of TDD before implementing.
3. Write a minimal, MECE set of tests; implement and iterate against the tests; surgically update docs.

---

## Current Issues

### Code Duplication

- [ ] **Recursive data traversal** in `shorten_data()` and `extract_text_from_content()` (both in `scripts/conversations/utils.py`) uses very similar dict/list/str handling patterns.
  `effort::low`

### Mixed Concerns

- [ ] **`cmd_parse()` (in `scripts/conversations/commands.py`)** currently covers a fairly wide set of responsibilities:
  - Input resolution
  - Content reading
  - Conversation parsing
  - **Agent file handling (in `scripts/conversations/commands.py`)** – about 80 lines of relatively complex logic inside an already long function
  - Slice application
  - Metadata printing
  - Output formatting decisions

  Consider extracting agent file handling into separate function.

- [ ] **`main()` (in `scripts/conversations/cli.py`)** sets up four different `argparse` configurations inline, one per subcommand. These might be easier to manage as separate `parse_*_args()` helper functions.

### Other Maintainability

- [ ] **Inconsistent error handling** – a mix of `sys.exit(1)`, silent `continue`, and returning empty collections
  `priority::low`

---

## Known Technical Debt

### Fragile Functions

- [ ] **`is_system_message()` is fragile (in `scripts/conversations/parsing.py`)** – Currently uses naive string matching ("is running" in line) to distinguish system messages from user input. Both start with "> " prefix, making this distinction brittle. The inline comment states: "I hate this function, any other way would be better."

---
## Maintenance Guidelines

Postpone formatting and rendering of structured data as long as possible—ideally to the later stages of the flow. Think of a classic web server: data is turned into HTML *last* on the server, and rendered to the user *even later* in the client browser. This tool should follow the same approach. Formatting and/or rendering data is essentially irreversible, while structured data is malleable.

---


## Random Ideas

Not urgent, not necessarily important. Jotting down to not forget.

1. **Inject CLAUDE.md every 100K tokens** - Periodic reminders from global/local project settings

2. **Link tool inputs to their outputs** - Sometimes the connection isn't clear. Example:
  ```xml
  <tool-input name="Read" file_path="path/to/file.ext"></tool-input>
  </assistant-response>
  <user-message i="28">
  <tool-output>
       1→name: Maintain Documentation
       2→
       3→on:
  ```
  The gap makes it hard to see which output corresponds to which input.
3. **`--tools=input` or `--tools=output` flags** - Show only tool inputs or only outputs (not both)

4. **`-u`, `--usage` flag** - Display token usage statistics from conversation file

### Support Other Message Types

1. **Support `is_error: true` in `tool_result` messages**

Properly detect and handle tool errors from raw JSON input.
Example structure:
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_014bCRg7RwRcFP4trWqEGfs2",
        "content": "...",
        "is_error": false
      }
    ]
  }
}
```


2. **Support `AskUserQuestion` tool**

Example data:

Tool input:
```json
{
  "userType": "external",
  "message": {
    "id": "msg_01JpyzXxytSHeAkm8biC8yPt",
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01TeNVELpSD15XCpJYUhp6s8",
        "name": "AskUserQuestion",
        "input": {
          "questions": [
            {
              "question": "Where should the reading time (e.g., '4 min read') come from?",
              "header": "Read time",
              "options": [
                {
                  "label": "Estimate from TLDR markdown length",
                  "description": "Calculate ~200 words/minute from the TLDR content when available"
                },
                {
                  "label": "Skip reading time for now",
                  "description": "Just show source name without reading time estimate"
                },
                {
                  "label": "Use article.articleMeta if available",
                  "description": "Some sources already provide reading time in articleMeta field"
                }
              ],
              "multiSelect": false
            },
            {
              "question": "What should the 'Mark Done' (checkmark) action do?",
              "header": "Done action",
              "options": [
                {
                  "label": "Mark as Read only",
                  "description": "Set isRead=true, article stays visible but muted"
                },
                {
                  "label": "Mark as Removed",
                  "description": "Set removed=true, article goes to bottom with strikethrough"
                },
                {
                  "label": "Both: Read + Removed",
                  "description": "Set both isRead=true AND removed=true"
                }
              ],
              "multiSelect": false
            },
            {
              "question": "Should I create separate plans for each gesture, or combine them?",
              "header": "Plan scope",
              "options": [
                {
                  "label": "3 separate plans (Recommended)",
                  "description": "Plan A: Header + Actions, Plan B: Swipe-Down, Plan C: Overscroll-Up"
                },
                {
                  "label": "2 plans: Header + All Gestures",
                  "description": "Plan A: Header + Actions, Plan B: Both gestures together"
                }
              ],
              "multiSelect": false
            }
          ]
        }
      }
    ],
  },
  "type": "assistant",
  "uuid": "dee79cab-27f0-4ded-a38b-b4e37b5a8032",
}
```

Tool Output:
```json
{
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "content": "User has answered your questions: \"Where should the reading time (e.g., '4 min read') come from?\"=\"Use article.articleMeta if available\", \"What should the 'Mark Done' (checkmark) action do?\"=\"Mark as Removed\", \"Should I create
 separate plans for each gesture, or combine them?\"=\"3 sepearate plans — Plan A: Header + Actions, Plan B: Swipe-Down, Plan C: Overscroll-Up. and this user ask form didn't have a section for your question 2 about where to get the Favicon. then dispatch
a single-subsystem agent with this question exactly. \"i want to use the article's favicon in the zen overlay, tell me how the app handles favicons now so i can stay consistent when integrating it into the zen overlay\"\". You can now continue with the us
er's answers in mind.",
        "tool_use_id": "toolu_01TeNVELpSD15XCpJYUhp6s8"
      }
    ]
  },
  "toolUseResult": {
    // repetition of the questions and options from the tool use input
    "questions": [
      {
        "question": "Where should the reading time (e.g., '4 min read') come from?",
        "header": "Read time",
        "options": [
          {
            "label": "Estimate from TLDR markdown length",
            "description": "Calculate ~200 words/minute from the TLDR content when available"
          },
          {
            "label": "Skip reading time for now",
            "description": "Just show source name without reading time estimate"
          },
          {
            "label": "Use article.articleMeta if available",
            "description": "Some sources already provide reading time in articleMeta field"
          }
        ],
        "multiSelect": false
      },
      {
        "question": "What should the 'Mark Done' (checkmark) action do?",
        "header": "Done action",
        "options": [
          {
            "label": "Mark as Read only",
            "description": "Set isRead=true, article stays visible but muted"
          },
          {
            "label": "Mark as Removed",
            "description": "Set removed=true, article goes to bottom with strikethrough"
          },
          {
            "label": "Both: Read + Removed",
            "description": "Set both isRead=true AND removed=true"
          }
        ],
        "multiSelect": false
      },
      {
        "question": "Should I create separate plans for each gesture, or combine them?",
        "header": "Plan scope",
        "options": [
          {
            "label": "3 separate plans (Recommended)",
            "description": "Plan A: Header + Actions, Plan B: Swipe-Down, Plan C: Overscroll-Up"
          },
          {
            "label": "2 plans: Header + All Gestures",
            "description": "Plan A: Header + Actions, Plan B: Both gestures together"
          }
        ],
        "multiSelect": false
      }
    ],
    // `answers` might be interesting
    "answers": {
      "Where should the reading time (e.g., '4 min read') come from?": "Use article.articleMeta if available",
      "What should the 'Mark Done' (checkmark) action do?": "Mark as Removed",
      "Should I create separate plans for each gesture, or combine them?": "3 sepearate plans — Plan A: Header + Actions, Plan B: Swipe-Down, Plan C: Overscroll-Up. and this user ask form didn't have a section for your question 2 about where to get the Favicon. then dispatch a single-subsystem agent with this question exactly. \"i want to use the article's favicon in the zen overlay, tell me how the app handles favicons now so i can stay consistent when integrating it into the zen overlay\""
    }
  }
}
```


3. **Support embedded "command-message" in user messages**

Example data:
```json
{
  "parentUuid": null,
  "isSidechain": false,
  "userType": "external",
  "cwd": "/Users/giladbarnea/dev/TLDRScraper",
  "sessionId": "5410385c-b6ca-4add-af24-386832fee304",
  "version": "2.0.75",
  "type": "user",
  "message": {
    "role": "user",
    "content": "<command-message>plan</command-message>\n<command-name>/plan</command-name>\n<command-args>we are working by thoughts/25-12-22-zen-overlay-header-and-swipe-interactions/discussion.md. Ultrahink in this order: 1. This is a compound feature. It might as well be broken down to individual User stories, therefore justifying multiple Plans (one for each user story). Therefore, plan *recursively*: Which user stories is this specification composed of? 2. For each sub-user-story, plan well: how to approach this → what would be required for a good, working, simple implementation?</command-args>"
  },
  "uuid": "5228a544-0a8b-4bd4-a1fb-8b9a965141ad",
  "timestamp": "2025-12-22T19:46:22.632Z"
}
```

4. **Support `TodoWrite` tool**

Tool input:
```json
{
  "type": "assistant",
  "userType": "external",
  "message": {
    "type": "message",
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_01FDek4CDQPVwv7fp5GSVJ3e",
        "name": "TodoWrite",
        "input": {
          "todos": [
            {
              "content": "Write Plan A: Header Redesign + Actions (US1, US2, US3, US6)",
              "status": "in_progress",
              "activeForm": "Writing Plan A: Header Redesign + Actions"
            },
            {
              "content": "Write Plan B: Swipe-Down Collapse Gesture (US4)",
              "status": "pending",
              "activeForm": "Writing Plan B: Swipe-Down Gesture"
            },
            {
              "content": "Write Plan C: Overscroll-Up Completion Gesture (US5)",
              "status": "pending",
              "activeForm": "Writing Plan C: Overscroll-Up Gesture"
            }
          ]
        }
      }
    ],
  }
}
```

And matching tool output:
```json
{
  "parentUuid": "89d85c67-8531-41d7-8dd2-f8f5f4d1366c",
  "isSidechain": false,
  "userType": "external",
  "cwd": "/Users/giladbarnea/dev/TLDRScraper",
  "sessionId": "5410385c-b6ca-4add-af24-386832fee304",
  "version": "2.0.75",
  "gitBranch": "zen-overlay-header-and-swipe-interactions",
  "slug": "deep-wobbling-book",
  "type": "user",
  "message": {
    "role": "user",
    "content": [
      {
        "tool_use_id": "toolu_01FDek4CDQPVwv7fp5GSVJ3e",
        "type": "tool_result",
        "content": "Todos have been modified successfully. Ensure that you continue to use the todo list to track your progress. Please proceed with the current tasks if applicable"
      }
    ]
  },
  "uuid": "bbd46b50-6b06-4946-a050-5e89f83933bc",
  "timestamp": "2025-12-22T19:55:51.587Z",
  "toolUseResult": {
    "oldTodos": [],
    "newTodos": [
      {
        "content": "Write Plan A: Header Redesign + Actions (US1, US2, US3, US6)",
        "status": "in_progress",
        "activeForm": "Writing Plan A: Header Redesign + Actions"
      },
      {
        "content": "Write Plan B: Swipe-Down Collapse Gesture (US4)",
        "status": "pending",
        "activeForm": "Writing Plan B: Swipe-Down Gesture"
      },
      {
        "content": "Write Plan C: Overscroll-Up Completion Gesture (US5)",
        "status": "pending",
        "activeForm": "Writing Plan C: Overscroll-Up Gesture"
      }
    ]
  }
}
```

### Support Forked Conversations

This idea is slightly more complex because it involves cross-session references, thus more than one session file. For example, `92dba0e7-df21-4a0b-b5c3-e3742e691186` is a fork of `95af138f-4005-42e9-9956-0b13e262cf0b`. Messages from either session are intertwined. Need to understand the patterns. Do origin messages have another shape?

Observations from one fork case: The first object with the forked sessionId was the first `"type": "user"` object; all objects before it were not user/assistant messages. Also, objects with the forked sessionId may share the same `slug` field value (low confidence).
