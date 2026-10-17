# EU Company Register Tracker

A free, open directory of Europe's official company registers, with a live status check.

For each register: the official site, whether there's a free API, the API docs, whether you need a key or account, what data you get, documented rate limits, and the licence or terms. Every fact links to the official page it came from, with the date it was checked. Anything we couldn't confirm on an official page is marked **Unverified**. We don't guess.

**v1 covers:** Czechia (ARES), Poland (KRS), France (API Recherche d'entreprises), Finland (PRH/YTJ), Norway (Brønnøysund), Denmark (CVR), Estonia (e-Business Register), Netherlands (KVK), Belgium (KBO/BCE), Germany (Handelsregister), Austria (Firmenbuch), Spain (BORME), plus the EU VAT check (VIES), the EU-wide register search (BRIS) and Switzerland (Zefix).

## Live status

`scripts/check_status.py` makes **one** light GET request per register and writes `status.json`:

| state | meaning |
|---|---|
| `up` | the endpoint answered as expected (for Zefix: an auth challenge, since it needs credentials) |
| `limited` | it answered with HTTP 429 (rate-limited) |
| `maintenance` | a maintenance page came back instead of data |
| `degraded` | an unexpected status or content type |
| `down` | no response, or a 5xx error |
| `unknown` | bot protection in front of the site; we can't tell |

When a state changes, a dated entry is added to `data/changelog.json`. `.github/workflows/status.yml` runs this every 6 hours and commits the result.

## Run it locally

```bash
python3 scripts/check_status.py       # writes status.json (stdlib only, no installs)
python3 scripts/build.py              # writes index.html, changelog.html, registers/*.html
python3 -m http.server 8000           # open http://localhost:8000
```

## Files

- `data/registers.json`: the facts. Each field has `value`, `source`, `checked`, `verified`.
- `data/changelog.json`: dated changes (manual entries plus automatic status changes).
- `status.json`: the latest check, with a short history per register.
- `scripts/`: the status check and the static site builder.

## Corrections

Spotted something wrong or out of date? Open an issue with a link to the official source.

## Licence

Code: MIT (see `LICENSE`). Facts are summaries of, and link to, each register's own pages; their data stays under the register's own licence or terms.

Not affiliated with any register or authority. Not legal advice.
