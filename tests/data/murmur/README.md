# Curated murmur dataset

Files:
- `labels.yaml`: hand-labeled murmur positives per session. Unlisted assistant messages are negatives.
- `raw/<session_id>.json`: raw `ccc <session_id> --only-assistant -f json` export.
- `dataset.jsonl`: flattened one-row-per-assistant-message dataset for tests and evals.

Row schema:
- `example_id`: stable `<session_id>:<original_index>` key
- `session_id`
- `original_index`
- `model`
- `text`
- `is_murmur`
- `difficulty`: `standard` or `tricky`

`tricky` marks positives that the first POS-backed pass may miss without counting that as a regression.
