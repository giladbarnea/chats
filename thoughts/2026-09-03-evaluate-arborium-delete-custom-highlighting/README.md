# Evaluate Arborium and delete custom highlighting

**Priority: P2**

## Problem statement

The current Rust syntax-highlighting implementation adds roughly **3,000 maintained lines** across:

- The custom lexer engine
- Seven language tables
- Generators
- Alias and style data
- Supporting integration code

The implementation works and is gated. The seven supported families cover **98.2% of painted characters**:

- TypeScript
- TSX
- Bash/sh/zsh
- Python
- JavaScript
- JSON
- SQL

The goal is not to add Arborium beside this code. The goal is to determine whether Arborium can replace it and let us delete most custom implementation.

## Reproduction and evaluation

Use the existing held-out corpus and Arborium probes:

1. Run Arborium against the same held-out real snippets.
2. Include all seven current language families.
3. Measure:
   - Visible Monokai-style agreement
   - Painted recall
   - Painted precision
   - Parse failures
   - Runtime and peak memory
4. Inspect the lowest-agreement snippets side by side.
5. Integrate Arborium behind the existing renderer interface in a temporary branch.
6. Run the existing renderer, fence, colored-output, and G4 gates.
7. Compare deleted custom lines against new adapter and configuration code.

The team proposed these go bars:

- At least **90% weighted style agreement**
- At least **80% painted recall per major family**
- Zero parse failures

## Existing evidence

The initial Arborium experiment found:

- **93.5%** weighted style agreement
- **1,905/1,905** snippets parsed
- TypeScript: 91.6%
- TSX: 90.6%
- Bash: 96.9%
- Python: 89.3%
- Fast runtime and about 35 MB peak memory

JSON and Markdown were not measured in that experiment. The final shipped set uses JSON but not Markdown, so JSON remains the important missing measurement.

## Team-recorded fix vector

Arborium can replace **both the custom engine and language tables**, not only the tables.

Keep the existing renderer geometry, styles, color downgrade, search highlighting, and output sinks. Replace the lexer layer with:

- Arborium language selection
- Byte-span adaptation
- A small capture-name-to-style map per language

The team explicitly said the held-out corpora and gates should survive. They are the evidence used to judge Arborium and must not be deleted with the implementation.
