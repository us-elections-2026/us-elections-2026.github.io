# Opus Handoff: Data Reliability Improvements

Please improve this Quarto + GitHub Pages repo with a focus on data reliability.

## Context

- Static Quarto site for a Korean-language 2026 U.S. midterm election briefing.
- Data lives in `data/*.json` and `data/*.csv`.
- `R/helpers.R` renders tables and HTML snippets from those files.
- GitHub Actions renders Quarto and publishes to `gh-pages`.
- Main project risk: stale or malformed data silently rendering into public pages.

## Requested Changes

### 1. Add Data Schema Documentation

Create `data/README.md`.

Document each data file, including:

- Required fields or columns.
- Nullable fields.
- Sign conventions.
- Pages and helper functions that consume the file.

Important conventions to state explicitly:

- Margins are always normalized as `positive = Democratic advantage`.
- Unknown values should remain `null` in JSON and render as `—` or `【수집】`.
- Preserve provenance fields such as `type`, `population`, `*_as_of`, `source_label`, and `provenance_note` where present.
- Do not fill missing values with estimates.

### 2. Add Lightweight Data Validation

Prefer R for consistency with the current build stack: `scripts/validate_data.R`.

The script should:

- Validate JSON and CSV parseability.
- Check required top-level keys such as `as_of` where applicable.
- Check required columns for `data/korea_watch.csv` and `data/polls_log.csv`.
- Check important numeric/sign conventions where feasible.
- Fail with clear, actionable error messages.

Suggested validation targets:

- `data/forecast.json`
- `data/generic_ballot.json`
- `data/approval.json`
- `data/senate_races.json`
- `data/senate_primaries.json`
- `data/model_dashboard.json`
- `data/house_races.json`
- `data/national_econ.json`
- `data/candidates.json`
- `data/trends.json`
- `data/korea_watch.csv`
- `data/polls_log.csv`

Keep validation lightweight. The goal is to catch malformed data, missing required fields, and obvious convention violations before Quarto render.

### 3. Wire Validation Into GitHub Actions

Update `.github/workflows/publish.yml` so validation runs before Quarto publish.

Example shape:

```yaml
- name: Validate data schemas
  run: Rscript scripts/validate_data.R
```

Place this after R package installation and before the Quarto publish step.

### 4. Update README

Update `README.md` so it matches the current repository structure.

At minimum, include:

- Current main pages: `dashboard.qmd`, `house.qmd`, `national.qmd`, `korea-watch.qmd`, `methodology.qmd`, `scenarios.qmd`.
- `states/` pages.
- `assets/dashboard.{js,css}`, `assets/trends.js`, `assets/econ.js`, and candidate images.
- Current `data/` files.
- `scripts/` automation and API fetchers.
- The validation command once added.

### 5. Check `AGENTS.md`

`AGENTS.md` is currently untracked.

Please decide whether it should be committed. Since it contains important project instructions, the likely answer is to add it to git unless there is an intentional reason to keep it local-only. Do not ignore it without explaining why.

## Constraints

- Keep changes scoped and conservative.
- Do not invent missing data.
- Do not change existing data values unless required to fix a clear schema or parse issue.
- Preserve the current Quarto architecture.
- Respect the project conventions in `AGENTS.md`.
- Run local validation and `quarto render` before finishing.

## Suggested Final Verification

Run:

```bash
Rscript scripts/validate_data.R
quarto render
git status --short
```

In the final summary, report:

- Files changed.
- Validation result.
- Quarto render result.
- Any data files or schema assumptions that still need human review.
