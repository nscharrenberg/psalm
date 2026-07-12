## Environment variables
### Three-level fallback chain

| Priority | Scope | Example keys |
|---|---|---|
| 1 (highest) | Per-agent | `PSALM_JUROR_2_MODEL`, `PSALM_PROSECUTOR_BASE_URL` |
| 2 | Jury-wide (jurors only) | `PSALM_JURY_MODEL`, `PSALM_JURY_BASE_URL` |
| 3 | Global | `PSALM_MODEL`, `PSALM_BASE_URL`, `PSALM_API_KEY` |

### Full variable reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `PSALM_API_KEY` | Yes* | — | Global api key; `SystemExit` if no role/jury/juror key covers a role |
| `PSALM_BASE_URL` | No | `https://api.openai.com/v1` | Global base URL |
| `PSALM_MODEL` | No | `gpt-4o-mini` | Global model |
| `PSALM_TEMPERATURE` | No | `0.1` | Global temperature |
| `PSALM_{ROLE}_API_KEY` | No | `PSALM_API_KEY` | Role override; ROLE ∈ {PROSECUTOR, DEFENSE, JUDGE} |
| `PSALM_{ROLE}_BASE_URL` | No | `PSALM_BASE_URL` | Role override |
| `PSALM_{ROLE}_MODEL` | No | `PSALM_MODEL` | Role override |
| `PSALM_{ROLE}_TEMPERATURE` | No | `PSALM_TEMPERATURE` | Role override |
| `PSALM_JURY_API_KEY` | No | `PSALM_API_KEY` | Jury-wide key fallback |
| `PSALM_JURY_BASE_URL` | No | `PSALM_BASE_URL` | Jury-wide base URL fallback |
| `PSALM_JURY_MODEL` | No | `PSALM_MODEL` | Jury-wide model fallback |
| `PSALM_JURY_TEMPERATURE` | No | `PSALM_TEMPERATURE` | Jury-wide temperature fallback |
| `PSALM_JUROR_{i}_API_KEY` | No | `PSALM_JURY_API_KEY` | Per-juror key; i = 0-based index |
| `PSALM_JUROR_{i}_BASE_URL` | No | `PSALM_JURY_BASE_URL` | Per-juror base URL |
| `PSALM_JUROR_{i}_MODEL` | No | `PSALM_JURY_MODEL` | Per-juror model |
| `PSALM_JUROR_{i}_TEMPERATURE` | No | `PSALM_JURY_TEMPERATURE` | Per-juror temperature |
| `PSALM_JUROR_{i}_SEED` | No | `i` | Per-juror seed (defaults to index for diversity) |
| `PSALM_JURY_SIZE` | No | `3` | Number of jurors (minimum 3) |
| `PSALM_ARGUMENTATION_ROUNDS` | No | `3` | Max rounds in argumentation phase |
| `PSALM_DELIBERATION_ROUNDS` | No | `2` | Max rounds in deliberation phase |
| `PSALM_TIME_LIMIT_SECONDS` | No | `120` | Overall wall-clock budget |
| `PSALM_DIMENSIONS` | No | `character,plot,world-building` | Comma-separated dimensions to evaluate. Valid: `character`, `plot`, `world-building`, `scenes-a-faire` |
| `PSALM_EVALUATION_STRATEGY` | No | `fully_separate` | Per-dimension pipeline strategy. Valid: `fully_separate`, `shared_arg_per_dim_deliberation`, `shared_all` |
| `PSALM_DEMO_SCENARIO` | No | `not-infringing` | Which target text to compare against `COPYRIGHT_TEXT`. Valid: `infringing`, `not-infringing` |

*If every role has its own key (`PSALM_PROSECUTOR_API_KEY` etc. and all jurors have `PSALM_JUROR_{i}_API_KEY` or `PSALM_JURY_API_KEY`), then `PSALM_API_KEY` is not required.

## Running the demo

```bash
export PSALM_API_KEY="sk-..."          # or point PSALM_BASE_URL at a local/compatible endpoint
python examples/main.py
```

Try the two scenarios and compare verdicts:

```bash
PSALM_DEMO_SCENARIO=infringing python examples/main.py       # expects a Guilty-leaning verdict
PSALM_DEMO_SCENARIO=not-infringing python examples/main.py   # expects a Not Guilty-leaning verdict
```

The demo prints the resolved configuration, the overall verdict and rationale, a per-dimension
verdict breakdown (`dimension`, `importance`, per-dimension verdict, weighted score), run metadata,
and the full `PSALMResult` as JSON.
