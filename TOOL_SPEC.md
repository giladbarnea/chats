# Tool Spec Definition

This document captures the **intended completion-truth definition** of the tool spec format.

It deliberately does **not** model buggy or overly permissive behavior from the current parser. The goal is to define the form we want to support and encourage.

## Top level

* `FILTERS := SPEC (WS SPEC)*`
* Repeated `-t` is equivalent to providing more `SPEC`s.
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

* `NAME := exact tool name`
* `DIRECTION := i | input | o | output`
* `ERROR := e | error`
* `SHORT := s | short`

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
* `s:o:Read`
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
