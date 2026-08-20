---
date: 2026-08-20
status: active
owner: captain-firstmate fleet
---

# Product-driven search and parse Rust rewrite

## Decision

The rewrite is product-driven. Common user journeys choose the work order, performance goals, and acceptance evidence.

The destination is fixed: three public journeys move to Rust. They are `ch search`, the default `ch [SESSION] [SLICE...]` session parse, and the separate `ch parse [FILE] [-f xml|json]` conversion subcommand. Every production dependency these journeys use also moves to Rust or leaves their path. Journey evidence controls how the fleet reaches that destination. This avoids another function-first rewrite that optimizes visible internals while missing common command shapes.

## Completion contract

The three journeys preserve their public arguments, output, ordering, errors, exit status, streaming behavior, and real-launcher behavior. Their production paths contain no Python implementation, callback, fallback, or parallel authority. Shared dependencies used by these journeys also move to Rust or leave their production paths.

Completion requires journey parity, package verification, the real installed launcher, and measured performance across representative search, session-parse, and conversion use cases.

## Control loop

1. Dispatch a scout, map, and profile team to map current journeys and costs.
2. Persist the accepted map before implementation starts.
3. Dispatch a rewrite team against the highest-impact coherent scope.
4. Persist its behavior proof, measurements, decisions, and remaining map.
5. Dispatch a new scout, map, and profile team against the changed system.
6. Repeat rewrite and remapping cycles.
7. Periodically dispatch an at-large code-design and bug review over all work since this fleet started.
8. Route accepted review findings into the next tests-first rewrite.
9. Stop only when the completion contract passes for all three public journeys.

## Durable context

Every delegate writes a succinct Markdown result under this directory. Files use ordered names such as `cycle-01-smp.md`, `cycle-01-rewrite.md`, and `review-01.md`.

The first mate maintains `state.md` as a short pointer list to the latest accepted files. New delegates receive file paths instead of reconstructed history. Each result must state its baseline, findings, decisions, proof, remaining risks, and exact next boundary.

## Chain of command

Gilad is the admiral. Main is the captain. The single outer teammate is the first mate.

The first mate delegates all exploration, implementation, testing, and review. It does not edit production source or tests. It may edit coordination Markdown in this directory and create local checkpoint commits after accepted cycles. It does not push.

The captain communicates only with the first mate. The first mate communicates with its crews, keeps their contexts safe, and escalates only product decisions, scope changes, blockers, or the accepted final result.
