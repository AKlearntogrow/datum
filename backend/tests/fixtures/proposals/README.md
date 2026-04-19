# Proposal fixtures

Canonical LLM outputs captured from real Proposer runs. Used by tests to
verify our Pydantic models parse real Claude output — without spending
API credits on every test run.

## Naming convention

`<warehouse>_<prompt_version>.json` — e.g., `messy_warehouse_v0.json`
is the output produced when running the v0 system prompt against the
synthetic messy_warehouse database.

## Regenerating

To refresh a fixture, run the proposer smoke test, then move the output:

```bash
backend/.venv/Scripts/python backend/scripts/smoke_proposer.py
mv proposer_smoke_output.json backend/tests/fixtures/proposals/<warehouse>_<prompt_version>.json
```

Regeneration is expected only when:

- A prompt version is bumped (v0 -> v1, etc.)
- The synthetic warehouse schema changes in a way that should produce materially different proposals

Normal test runs use the stored fixture; regeneration is a deliberate act.
