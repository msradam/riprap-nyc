<!-- Thanks for opening a PR. The checklist below mirrors how Riprap
     was kept stable through hackathon week. -->

## Summary

<!-- One paragraph: what changed, and why. Reference issues with #N. -->

## Tested against

- [ ] Local dev server (`uvicorn web.main:app`)
- [ ] Local Docker (`docker compose up`)
- [ ] Hosted lablab Space
- [ ] Self-hosted GPU inference

## Stones-fire probe

<!-- Paste the tail of `scripts/probe_stones_fire.py` output. The PR
     should not be merged unless all five Stones fire. -->

```
PYTHONPATH=. uv run python scripts/probe_stones_fire.py --timeout 600
```

## Energy-ledger sanity check

<!-- If this PR touches inference, app/emissions.py, or app/llm.py:
     paste the n_measured / n_calls ratio and confirm hardware label. -->

## Checklist

- [ ] No regression in `app/`, `web/`, `services/`, or
      `inference-vllm/proxy.py` logic (typo-only edits OK).
- [ ] Docs updated (`README.md`, relevant `docs/*.md`) if public
      surface changed.
- [ ] `CHANGELOG.md` entry under `[Unreleased]` with the right
      `Added` / `Changed` / `Fixed` bucket.
- [ ] Conventional-commit prefix on the squash title
      (`feat:` / `fix:` / `docs:` / `chore:` / `build:`).
