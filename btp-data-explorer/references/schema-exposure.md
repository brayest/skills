# `exposure` schema (exposure-service)

The core of the platform. An **exposure** is a policy record; everything else hangs off it.
Only the granted (non-PII) tables are listed. `intake_comment*` and `deleted_record` are NOT
granted.

## Key entities

### `exposure.exposure` — the central fact table
One row per policy. Grows continuously.
- `id` (varchar PK), `status`, `status_date`, `exposure_type` = `REGISTER` (original) or
  `STATEMENT` (renewal), `exposure_set_id` (→ `exposure_set`), `register_id`,
  `latest_statement_id`, `prev_register_id`, `next_register_id`
- `buyer_org_id`, `name`, `currency`, `total_insured_value` (BIGINT), `exposure_count` (BIGINT)
- `inception_date`, `expiration_date`, `tiv_calc_date`
- `reviewed_completeness`, `field_completeness` (NUMERIC 0–1)
- JSONB: `insured_values`, `metrics`, `subject_counts`, `locked`
- audit: `created_date`, `modified_date`, `created_by`, `modified_by`
- **In-force** = `inception_date <= now() AND expiration_date >= now()`.

### `exposure.exposure_set` — line of business grouping
- `id` (PK), `line_of_business` — join target for "by LOB" questions.

### `exposure.exposure_status` — lifecycle audit (fact)
One row per status transition. `exposure_id`, `status`, `old_status`, `status_date`.
Use for funnels and "time in status".

### `exposure.exp_org` — org ↔ exposure (tenancy)
- `exposure_id`, `org_id`, `org_type` (BUYER/FACILITATOR/SUPPLIER), `originator` (bool),
  `exposure_reference_number`. Use for org scoping; `originator = true` for the owning org.

### `exposure.exposure_period`
Coverage periods per exposure: `exposure_id`, `inception_date`, `expiration_date`, `due_date`,
`phase`, `submitted_on`, `renewal_period`.

### Time-series metric tables (fact, one row per snapshot)
- `exposure.metric_tiv` — `exposure_id`, `total_insured_value` (BIGINT), `property_count`,
  `currency_code`, `created_date`. TIV over time.
- `exposure.metric_field_completeness` — `field_completeness`, `address_completeness`,
  `primary_completeness`, `secondary_completeness`, `property_count`, `created_date`.
- `exposure.metric_reviewed_completeness` — `reviewed_completeness`, `property_count`.

### Intake / onboarding pipeline (ops)
- `exposure.intake_request` — `exposure_id`, `purpose` (ONBOARDING/EDIT_REPLACE),
  `status` (CREATED/CLEANSING/VALIDATING/COMPLETED), `submitted_date`, `validated_date`,
  `counters` (JSONB). Cycle time = `validated_date - submitted_date`.
- `exposure.intake_file` — `intake_request_id`, `category` (RAW/PROCESSED), `upload_status`,
  `size`, `content_type`, `created_date`.
- `exposure.intake_job` — `intake_file_id`, `queued_job_status`
  (QUEUED/PROCESSING/COMPLETED/FAILED), `failed_reason`, status dates. Failure-rate source.
- `exposure.bulk_exposure_job` / `bulk_exposure_job_item` — bulk import volume.

### Reference / config
- `exposure.line_of_business` (`code` PK, `name`), `exposure.renewal_config`,
  `exposure.statement_usage`, `exposure.exposure_exchange_rate` (applied FX rates),
  `exposure.due_date`.

## Common joins
- LOB: `exposure JOIN exposure_set ON exposure.exposure_set_id = exposure_set.id`.
- Org: `exposure JOIN exp_org ON exp_org.exposure_id = exposure.id`.
- Units: `property.exposure_unit.exposure_id = exposure.exposure.id`.

## Gotchas
- Filter `exposure_type = 'REGISTER'` when counting "policies" to avoid double-counting renewals.
- `total_insured_value` is BIGINT — confirm scale; don't sum across mixed `currency`.
- Status strings vary by env/config — `SELECT DISTINCT status FROM exposure.exposure` first.
