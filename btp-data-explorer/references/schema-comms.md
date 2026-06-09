# `email` and `helpcenter` schemas

Both small. Most of `email` is PII (recipient addresses + rendered bodies) and is **not
granted** — only `notification_eligibility` is.

## `email` schema (email-service)

Granted:
- `email.notification_eligibility` — one row per user: `user_id`, `opt_out` (bool),
  `invite_accepted` (bool), audit. Use for **opt-out rate** and **invite-acceptance rate**.
  - opt-out rate: `avg(opt_out::int)` or `count(*) filter (where opt_out) / count(*)`.

NOT granted (PII / content): `email.outbound_email` (request/response bodies contain recipient
emails + rendered content), `email.queued_notification` (notification content). So **email
*volume* / deliverability by template is not available** through this user. If a stakeholder
needs "emails sent per day by template", that requires a future column-level grant on the
non-PII columns (`sent_date`, `template_alias`, `resource_type`) — tell them it's out of scope
for now rather than improvising.

## `helpcenter` schema (helpcenter-service)

Granted:
- `helpcenter.term` — help articles / glossary: `id`, `title`, `content`, `category`, `source`,
  `tags` (text[]), `default_sort_order`, audit. Small reference set.
- `helpcenter.query_history` — search telemetry (fact): `id`, `request` (JSONB — the search
  criteria), `total_hits` (BIGINT), `created_date`.
  - **Top searches:** group by the query text extracted from `request` (inspect the JSONB shape
    first with `get_object_details` + a sample row).
  - **Zero-result searches** (content gaps): `where total_hits = 0`.
  - **Search volume over time:** count by `date_trunc('day', created_date)`.

## Gotchas
- `query_history.request` is JSONB; confirm its structure with a sample before extracting the
  search string (`request ->> 'query'` or similar — verify the key).
