# tech-news

How the system works (roles, schedules, commands): `docs/arnes.md`. Every action goes through the `tn` CLI (ADR-0004); never write to `data/tech-news.db` or `semanas/` by other means.

## Development

- Python 3.12 with `uv`. Install: `uv sync`. Run: `uv run tn --help`. Tests: `uv run pytest`.
- Source catalog: `fuentes.yaml` (adding a source needs no code). Data: `data/tech-news.db` (SQLite, gitignored).
- Tests never hit the network: parsers are tested against fixtures in `tests/fixtures/`.
- The Montador (phase 2) talks to CapCut only through `src/tn/capcut.py`, which shells out to capcut-kit cloned outside the repo (ADR-0005). Never copy capcut-kit code into this repo: it has no license.
- When running `tn` on the user's behalf from an interactive Claude Code session, pass `--origen claude` to the commands that accept it (`recoger`, `editar`, `explorar`, `diario` and the `historia` corrections). Role skills run headless (`editor`, `explorador`) follow their skill's commands exactly and never add `--origen`.

## Agent skills

### Issue tracker

Issues are tracked in this repo's GitHub Issues via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
