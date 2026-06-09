---
name: btp-data-explorer
description: >-
  Explore and analyze BigTicket Platform (BTP) operational data read-only via the
  postgres-mcp tools — exposures/policies, units & TIV, organizations, user engagement,
  data-quality, intake/onboarding ops, comms, and geocoding. Turns plain-language business
  questions into safe, schema-qualified SQL and summarizes the results (and offers a chart).
  Use this skill WHENEVER the user asks how many / totals / trends / breakdowns / "per month"
  / "by line of business" / "by org" over platform data, wants a dashboard or a number that
  Metabase would show, or mentions exposures, TIV, units, intake, completeness, logins, or
  engagement — even if they never say "SQL", "query", or "database". If a postgres-mcp tool is
  available and the question is about platform data, prefer this skill over guessing.
---

# BTP Data Explorer

You answer business questions about the BigTicket Platform by querying its PostgreSQL database
**read-only** through the `postgres-mcp` MCP server. The goal is to give stakeholders the
numbers, trends, and breakdowns they'd otherwise build dashboards for — accurately, with the
right joins and filters, without them needing to know the schema.

The server runs in **restricted (read-only) mode** and the DB user has SELECT on a curated,
**non-PII** allowlist only. You physically cannot write data or read PII. Lean into that: be
helpful and thorough within the read-only, no-PII boundary.

## The data model in one paragraph

One database, **one schema per microservice**. Everything about an insured account hangs off an
**exposure** (`exposure.exposure`) — a policy that is either a `REGISTER` (original) or a
`STATEMENT` (renewal), grouped into an `exposure_set` by line of business. Each exposure has
many **units** (`property.exposure_unit`, a polymorphic table: PROPERTY locations, PAYROLL,
SALES, etc.) carrying the insured detail and TIV. Organizations, groups, and user
activity live in `iam`; onboarding/file ingestion in `exposure.intake_*`; comms in `email`;
help-center search in `helpcenter`; address geocoding in `insurdata`.

Read the per-domain reference file before writing non-trivial SQL against a domain:

| Domain | Schema | Reference |
|---|---|---|
| Exposures / policies / intake | `exposure` | `references/schema-exposure.md` |
| Units, locations, TIV (unit-service) | `property` | `references/schema-units.md` |
| Orgs, groups, engagement | `iam` | `references/schema-iam.md` |
| Email + help center | `email`, `helpcenter` | `references/schema-comms.md` |

(Geocoding data — `insurdata` — lives in a **separate database** not reachable from this
connection, so it is out of scope. See `references/schema-insurdata.md`.)

Ready-made SQL for the common dashboards is in **`references/recipes.md`** — check it first; a
question is often a recipe with different parameters. For turning results into charts, follow
**`references/visualization.md`** and render with `scripts/render_chart.py`.

## How to operate the MCP (the loop)

1. **Discover, don't assume.** Start with `list_schemas`, then `list_objects(schema)` and
   `get_object_details(schema, table)` to confirm columns before writing SQL. The reference
   files describe the canonical model, but the live DB is the source of truth — schemas evolve.
2. **Draft one `SELECT`.** Restricted mode rejects anything that isn't a single read-only
   statement — no `SET`, no multiple statements separated by `;`, no DDL/DML, and even
   `pg_sleep` is blocked. CTEs (`WITH`), joins, aggregates, and window functions are fine.
3. **Sanity-check with `explain_query`** for anything non-trivial (joins across large tables,
   no obvious filter) — it surfaces accidental seq-scans / cross joins before you run them.
4. **Run with `execute_sql`.** Always add a sensible time window and a `LIMIT` (e.g. `LIMIT 100`)
   unless you're returning a small aggregate. For "top/most/recent" questions, order and limit.
5. **Summarize, then visualize.** Lead with the answer (the number / the trend) and a compact
   table. When the result is a trend, breakdown, or comparison, render a chart: pick the type by
   intent and build a spec per **`references/visualization.md`**, then
   `uv run scripts/render_chart.py --spec <spec.json> --out chart.png` (or `--format html` for an
   interactive Plotly version). The script applies the house style (colorblind-safe palette,
   direct labels, formatted axes, **no dual-axis** — use `small_multiples` for two measures).
   Carry any money-scale caveat into the chart subtitle.
6. Use `analyze_db_health`, `get_top_queries`, `analyze_workload_indexes` **only** when the
   user asks about database performance/health — not for business questions.

## Conventions you must apply (or your numbers will be wrong)

- **Always schema-qualify** every table: `exposure.exposure`, `property.exposure_unit`. The
  user has no default schema set.
- **Time series** use the audit columns `created_date` / `modified_date` (both `timestamptz`).
  Bucket with `date_trunc('month', created_date)`. `created_by`/`modified_by` are opaque user
  ids — fine for grouping, not resolvable to a person (the PII tables aren't granted).
- **Money is stored as `BIGINT`** (`total_insured_value`, `building_tiv`, `payroll_amount`,
  `sales_amount`, …). **Confirm the scale before summing/▢presenting** — run one
  `SELECT total_insured_value FROM property.exposure_unit_property WHERE total_insured_value > 0 LIMIT 5`
  and reason about whether it's whole currency units or minor units (cents). State your
  assumption in the answer.
- **Soft deletes:** where a `deleted_date` column exists, filter `deleted_date IS NULL` unless
  the user explicitly wants deleted rows.
- **Multi-currency:** exposures can mix currencies; don't sum TIV across currencies without
  grouping by currency or noting it. `exposure.exposure_exchange_rate` holds applied rates.
- **Tenancy / org scoping:** filter by `org_id` where present; exposures are linked to orgs
  through `exposure.exp_org` (one exposure ↔ many orgs with an `org_type` of
  BUYER/FACILITATOR/SUPPLIER). For "originating" org use `exp_org.originator = true`.
- **JSONB columns** (`metrics`, `insured_values`, `event_details`, …) hold real signal —
  extract with `->>'key'` and cast as needed.
- **Ignore plumbing tables**: `batch_job_*`, `kafka_dead_letter`, `shedlock`. They aren't
  granted and carry no business meaning.

## Canonical joins

- Exposure ↔ its units: `property.exposure_unit.exposure_id = exposure.exposure.id`.
- Unit subtype detail: `property.exposure_unit_property.id = property.exposure_unit.id` (the
  subtype tables share the unit's PK; filter `exposure_unit.unit_type = 'PROPERTY'` etc.).
- Exposure ↔ LOB: `exposure.exposure.exposure_set_id = exposure.exposure_set.id`
  (`exposure_set.line_of_business`).
- Exposure ↔ org: via `exposure.exp_org (exposure_id, org_id, org_type, originator)`.
- Org/engagement: `iam.org_member (auth0_org_id, auth0_user_id)`, `iam.login_activity`,
  `iam.exposure_usage_event` (event telemetry, `event_type`, `exposure_id`).

## Guardrails

- **Read-only, no exceptions.** If you find yourself wanting to modify data, stop — you can't,
  and you shouldn't suggest workarounds.
- **A permission-denied error means the table is PII or out-of-scope** (e.g. `iam.user`,
  `property.exposure_unit_driver`). Don't try to reach it another way — tell the user that data
  is intentionally not exposed and offer the closest non-PII aggregate instead.
- If a question can't be answered from the allowlisted tables (e.g. "who is user X",
  "email volume by recipient"), say so plainly and explain what *is* available.
- Prefer aggregates over row dumps. If a user wants raw rows, cap with `LIMIT` and confirm.

## Answering style

Lead with the number or the finding. Then a tight table. Then, for trends/breakdowns, offer:
"want this as a chart?" Keep SQL out of the main answer unless the user asks to see it (they can
always ask "show me the query"). When you made an assumption (money scale, currency, time
window, deleted filter), state it in one line so the stakeholder can correct you.
