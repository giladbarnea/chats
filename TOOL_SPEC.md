# Tool Spec Definition

This document captures the **intended completion-truth definition** of the tool spec format.

It deliberately does **not** model buggy or overly permissive behavior from the current parser. The goal is to define the form we want to support and encourage.

Short values and progressive behavior are defined by [SHORT_SPEC.md](SHORT_SPEC.md).

## Top level

* `FILTERS := SPEC (WS SPEC)*`
* Tool filters accept all four carriers: `-t FILTERS`, `-t:FILTERS`, `--tools FILTERS`, and `--tools=FILTERS`.
* Repeating a carrier is equivalent to providing more `SPEC`s.
* Cross-`SPEC` validation is intentionally out of scope.
* After a space, state resets to a fresh `SPEC`.

Examples of equivalent top-level usage:

* `-t Read:o -t Bash:i`
* `-t "Read:o Bash:i"`

## One `SPEC`

* `SPEC := [!] ITEM ( ":" ITEM )*`

Where:

* `!` is optional
* `!` may appear **only at the very beginning**
* `!` may appear **at most once**
* `ITEM` is one of:

  * `NAME`
  * `DIRECTION`
  * `ERROR`
  * `SHORT`

And:

* no leading `:`
* no trailing `:`
* no `::`
* no bare `!`
* no `!!...`

## Item kinds

* `NAME := canonical tool name | known provider-native tool name | exact unknown tool name`
* `DIRECTION := i | input | o | output`
* `ERROR := e | error`
* `SHORT := s [=SHORT_SPEC] | short [=SHORT_SPEC]`
* `SHORT_SPEC :=` the grammar in [SHORT_SPEC.md](SHORT_SPEC.md)

## Name equivalence

An exact name always matches. Known provider-native and canonical names also match symmetrically, so `exec_command` and `Bash` select the same Codex command tools.

For Codex, `Bash` matches `exec_command`, `exec`, `shell`, and `shell_command`. `Patch` matches `apply_patch`.

A result's explicit parsed name and candidate aliases take priority. A nameless result inherits its call name through the tool ID map.

Unknown names retain exact matching. Alias normalization does not make all tool names case-insensitive.

## Distinct-slot rule

Think of a `SPEC` as filling 4 slots:

* `name`
* `direction`
* `error`
* `short`

Each `ITEM` fills exactly one slot.
A slot may be filled **at most once**.

So:

* `Read:o:s` is valid
* `o:Read` is valid
* `o:i` is invalid, because `direction` is already filled
* `s:short` is invalid, because `short` is already filled
* `Read:Bash` is invalid, because `name` is already filled

This is the precise version of:

> once the `name` slot is filled, no later `ITEM` may be a `NAME`

More generally:

> once any slot is filled, no later `ITEM` may target that same slot

## Colon rule

After an `ITEM`, `:` is valid **if and only if** at least one of the 4 slots is still unfilled.

So:

* `Bash` → `:` valid
* `Bash:o` → `:` valid
* `Bash:o:e` → `:` valid
* `Bash:o:e:s` → `:` invalid

This avoids false positives such as incorrectly rejecting the valid in-progress form:

* `Bash:o<typing a colon now>`

## State machine

### Start of `SPEC`

Valid next tokens:

* `!`
* `NAME`
* `DIRECTION`
* `ERROR`
* `SHORT`

Invalid next tokens:

* `:`
* end

### After `!`

Valid next tokens:

* `NAME`
* `DIRECTION`
* `ERROR`
* `SHORT`

Invalid next tokens:

* `!`
* `:`
* end

### After an `ITEM`

Valid next tokens:

* end
* space
* `:` **if some slot remains unfilled**

### After `:`

Valid next tokens:

* any `ITEM` whose slot is still unfilled

Invalid next tokens:

* `:`
* end
* any `ITEM` for an already-filled slot

## Valid examples

* `Read`
* `o`
* `!Read`
* `o:Read`
* `Read:o`
* `Read:o:s`
* `Read:o:s=80`
* `Read:o:s=p=128`
* `s=progressive=128`
* `s:o:Read`
* `s=10`
* `!Read:o:e`

## Invalid examples

* `!`
* `!!Read`
* `:Read`
* `Read:`
* `Read::o`
* `Read:Bash`
* `o:i`
* `s:short`
* `Read:o:output`
* `s=7`
* `s=abc`

## Short limits and precedence

[SHORT_SPEC.md](SHORT_SPEC.md) owns the value grammar, defaults, local inheritance, progressive sequence, and effective limits. A bare `SHORT` inherits the complete active global short policy. An explicit `SHORT=SHORT_SPEC` resolves its local policy under that contract.

When several visible positive specs match the same tool and more than one declares `SHORT`, the short value is chosen by specificity:

* `name`, `direction`, and `error` each add specificity
* the most specific matching short spec wins
* if specificity ties, the later matching short spec wins

Examples:

* `--short=10 -t:s` shortens regular messages and tools to 10
* `--short -t:s=10` shortens regular messages to 500 and tools to 10
* `--short=20 -t:s=10 -t:Bash:s=30` shortens regular messages to 20, non-Bash tools to 10, and Bash tools to 30
* `--short=p=128 -t:s` makes tools inherit the global progressive policy

## Practical scope

This definition is intentionally **per-spec**.

It does **not** attempt to validate contradictions or redundancies across multiple specs.
For example, forms like the following may still exist at the top level without being cross-validated here:

* `-t "Bash:i !Bash:i"`

That is outside the scope of this spec.

## Short summary

* A `SPEC` is an optional leading `!` plus a colon-separated sequence of `ITEM`s.
* Each `ITEM` fills one unique slot.
* No slot may be filled twice.
* `:` is allowed only between items, and only while some slot remains unfilled.
* The definition is intentionally stricter than the current parser, so it does not encourage buggy or undesirable forms.
