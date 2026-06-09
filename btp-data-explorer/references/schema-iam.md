# `iam` schema (iam-service)

Organizations, groups, permissions, and **engagement telemetry**. Identity PII lives in
`iam.user` and `iam.terms_acceptance` which are **NOT granted** — you cannot resolve a
`auth0_user_id` to a name or email. The opaque ids below are fine for counting/grouping.

## Org & membership
- `iam.organization` — `auth0_org_id` (PK), `display_name` (org name — business, not personal),
  `logo_location`, `brand_color`, audit. The org dimension.
- `iam.org_member` — membership join (fact-ish): `id` (PK), `auth0_org_id`, `auth0_user_id`,
  `last_login`, `exposure_count`, `group_count`, `deleted_at`, audit. Members per org;
  filter `deleted_at IS NULL` for active members.
- `iam.org_domain` — `auth0_org_id`, `domain_name`, `access_type` (OWNER/MANAGED/UNVERIFIED).
- `iam.duns_number` — business registry id → org. `iam.blacklist_domain` — blocked domains.

## Groups & permissions
- `iam.group` — hierarchical groups: `id`, `org_id`, `group_name`, `parent_group_id`, `path`,
  `user_count`, `exposure_count`, `external`.
- `iam.group_member` — `group_id`, `org_member_id`, `role` (ADMIN/MEMBER).
- `iam.group_role` / `iam.org_member_role` — fine-grained access grants:
  `resource_type` (EXPOSURE/UNIT/REGISTER/ORGANIZATION), `resource_id`, `relation`.
- `iam.permission_history` — grant/revoke audit (fact): `operation` (ADD/REMOVE),
  `org_member_id`, `group_id`, `relation`, `resource_type`, `resource_id`, `created_date`.

## Engagement telemetry (the DAU/MAU + adoption source)
- `iam.login_activity` — one row per login: `auth0_user_id`, `auth0_org_id`,
  `login_timestamp`, `created_date`. Active users/orgs over time.
- `iam.exposure_usage_event` — one row per interaction: `auth0_user_id`, `auth0_org_id`,
  `exposure_id`, `register_id`, `event_type` (VIEW/EDIT/DOWNLOAD/…), `event_details` (JSONB),
  `created_date`. Feature adoption, most-viewed exposures, per-org activity.

## Common patterns
- DAU/MAU per org: `count(distinct auth0_user_id)` from `login_activity` grouped by
  `date_trunc(...)` (+ `auth0_org_id`), optionally joined to `organization` for the name.
- Members per org: `org_member` grouped by `auth0_org_id` (filter `deleted_at IS NULL`).
- Engagement by event: `exposure_usage_event` grouped by `event_type` / day.

## Gotchas
- `auth0_user_id` is opaque — never claim it identifies a person; you can't join to a name.
- Distinguish **users** (distinct `auth0_user_id`) from **memberships** (`org_member` rows) —
  one user can belong to several orgs.
- `iam.group_role` / `org_member_role` describe *permissions*, not usage — don't confuse
  "has access to" with "used".
