from __future__ import annotations

import json
from pathlib import Path

from conversations.murmurs import analyze_murmur, is_murmur

DATASET_PATH = Path(__file__).parent / "data" / "murmur" / "dataset.jsonl"


def _load_dataset() -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_curated_murmur_dataset_counts_are_stable() -> None:
    dataset = _load_dataset()
    positive_count = sum(1 for row in dataset if row["is_murmur"])
    tricky_positive_count = sum(
        1
        for row in dataset
        if row["is_murmur"] and row["difficulty"] == "tricky"
    )

    assert len(dataset) == 53, f"Expected 53 curated assistant messages. Got: {len(dataset)}"
    assert positive_count == 13, f"Expected 13 murmur positives. Got: {positive_count}"
    assert tricky_positive_count == 4, (
        "Expected 4 tricky murmur positives kept for soft-recall evaluation. "
        f"Got: {tricky_positive_count}"
    )


def test_analyze_murmur_exposes_progressive_head_features() -> None:
    features = analyze_murmur("Now verifying the build.")

    assert features.tokens[:3] == ("Now", "verifying", "the"), (
        "Expected Treebank tokenization for the murmur prefix. "
        f"Got: {features.tokens!r}"
    )
    assert features.pos_tags[1] == ("verifying", "VBG"), (
        "Expected NLTK POS tagging to mark 'verifying' as VBG. "
        f"Got: {features.pos_tags!r}"
    )
    assert features.starts_with_now, "Expected 'Now' prefix to be detected."
    assert features.starts_with_progressive_verb, (
        "Expected the POS-backed feature extractor to notice the progressive verb head."
    )


def test_is_murmur_rejects_long_explanatory_status_update() -> None:
    text = (
        "Holding off on coding until I've mapped the actual control-plane surfaces "
        "and the ArticleCard press flow. Researching now."
    )
    assert not is_murmur(text), (
        "Expected long explanatory update to stay negative even though it opens with a gerund."
    )


def test_is_murmur_matches_all_strict_curated_rows() -> None:
    dataset = _load_dataset()
    strict_rows = [row for row in dataset if row["difficulty"] == "standard"]
    mismatches: list[str] = []

    for row in strict_rows:
        text = row["text"]
        if not isinstance(text, str):
            raise TypeError(f"Expected dataset text str. Got: {text!r}")
        actual = is_murmur(text)
        expected = bool(row["is_murmur"])
        if actual != expected:
            mismatches.append(f"{row['example_id']}: expected {expected}, got {actual} :: {text}")

    assert not mismatches, "Expected perfect accuracy on the strict murmur subset.\n" + "\n".join(mismatches)


def test_is_murmur_reaches_soft_recall_target_on_tricky_positives() -> None:
    dataset = _load_dataset()
    tricky_positives = [
        row for row in dataset if row["is_murmur"] and row["difficulty"] == "tricky"
    ]
    hits = 0

    for row in tricky_positives:
        text = row["text"]
        if not isinstance(text, str):
            raise TypeError(f"Expected dataset text str. Got: {text!r}")
        hits += int(is_murmur(text))

    assert hits >= 1, (
        "Expected the first POS-backed pass to recover at least one tricky murmur, "
        f"but it recovered {hits} of {len(tricky_positives)}."
    )
