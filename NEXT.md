# Next

State carried over from the old Mac on 2026-11-12.

## In flight
- Nothing uncommitted. `dev` is at 9b7c42f, equal to `origin/dev`, CI green. The last work (Oct 9) shipped the Gemini voice and assistant, per-subscriber memory, and `POST /api/laya/done/`.
- `feature/laya-tool-loop` (the `done/` endpoint) is already merged into `dev`; no work left there.
- The `feat/llm-responder-stub` branch (checked out in the sibling clone `not-maintained/aicell-api`, also on `origin`; tip `ea561a7`) has a history unrelated to `dev` (a base import, a CI workflow, then the stub), so it cannot merge into `dev`. Its keyword-fallback `llm_responder` is superseded by `api/assistant/agent.py` on `dev`. Treat it as parked.

## Next steps
1. Document `POST /api/laya/done/` in the Azerbaijani mobile guide: add a row and a section to `docs/mobile-integration.md` section 23 (laya), which lists only `plan/` and `narrate/`. Done when `rg -n "done/" docs/mobile-integration.md` shows the entry and, if the totals changed, the endpoint count (line 263 and section 26) matches `docs/api/*.md`.
2. Run `uv run ruff check . && uv run ruff format --check . && uv run pytest -q`. Done when all pass (about 100 s).

## Gotchas
- SQLite is the default DB; `DATABASE_URL` can point to PostgreSQL. `.env` and `db.sqlite3` are gitignored and do not travel; start from `.env.example` and set the `GEMINI_*` keys.
- A new `_()` string fails `test_every_code_string_is_translated`: run `manage.py sync_locale`, fill the az entries (Azerbaijani is the only non-English locale), run it again.
- `DEMO_AUTH` defaults to true (requests without a token act as a demo subscriber); `tests/settings.py` forces it false. Set `DEMO_AUTH=false` for real auth.
- Milvus Lite stores `data/knowledge.db` as a directory (gitignored); call `load_collection` before querying.
- `config/env.py` `text()` returns "" for an empty variable, so compose passes defaults as `${VAR:-value}`.
- Streaming `POST .../messages/` returns 200 with SSE; tests read it with `events(response)`.
