# `property` schema (unit-service)

Holds the **units** that make up an exposure — locations, payroll, sales, etc. — and the
detailed insured attributes. (Schema is named `property` for historical reasons.) PII subtypes
`exposure_unit_driver`, `exposure_unit_vehicle`, and `assignment` are NOT granted.

## Core polymorphic table

### `property.exposure_unit` — one row per unit (fact)
- `id` (varchar PK), `unit_type` (PROPERTY | PAYROLL | SALES | VEHICLE | DRIVER),
  `exposure_id` (→ `exposure.exposure`), `exposure_type`, `parent_id` (self-ref hierarchy),
  `root_id`, `group_id` (→ `unit_group`), `category_id` (→ `category`),
  `quality_score` (NUMERIC 0–1), `review_status`, `client_ref_id`, audit columns.
- Subtype detail tables share this PK (`subtype.id = exposure_unit.id`); filter by `unit_type`.

## Subtype detail (join on `id`)
- `property.exposure_unit_property` — **locations**. `address_country`, `address_area`
  (state/province), `address_city`, `address_postal`, `address_lat/lon`, `occupancy`,
  `construction`, `year_built`, `number_of_stories`, `number_of_buildings`, `floor_area_value`,
  `sprinklered`, `currency`, `total_insured_value` (BIGINT), `building_tiv`, `contents_tiv`,
  `bi_tiv`, `other_tiv`. The richest table for TIV-by-geography / occupancy / construction.
- `property.exposure_unit_payroll` — workers-comp. `class_system` (SIC/WC), `class_code`,
  `payroll_code`. Related: `payroll_class` (`payroll_amount`, `employee_count`, `hours_worked`,
  `area`, `class_code`), `payroll_mapping`, `payroll_mapping_amount`.
- `property.exposure_unit_sales` — general liability. `sales_type`, `country`, `area`,
  `sales_amount` (BIGINT), `class_code`.

## Grouping & quality
- `property.unit_group` (+ `unit_group_payroll`) — group container; `exposure_id`, `unit_type`,
  `review_status`, `quality_score`.
- `property.category` — per-exposure custom grouping (`exposure_id`, `category_name`).
- `property.metrics` — per-unit data quality: `exposure_unit_id`, `field_completeness`,
  `overall_metrics`/`field_scores` (JSONB).
- `property.activity_log` — unit change audit (fact): `exposure_id`, `exposure_unit_id`,
  `event_type`, `event_details` (JSONB), `created_date`. Good for activity/throughput; `created_by`
  is an opaque user id.

## Reference / lookup (filter `deleted_date IS NULL` where present)
- `ref_class_code` (NAICS/SIC/WC classification, full-text `search_vector`),
  `ref_occupancy`, `ref_construction`, `ref_building`, `ref_area` (country/area names),
  `ref_vehicle_classification(_category)`.

## Indexing / export (ops)
- `index_request` / `index_operation` (`status`, `job_execution_id`) / `index_rate` /
  `index_population` — rating runs. `export_schema`, `export_organization`, `exposure_export`.

## Common joins
- Units of an exposure: `exposure_unit.exposure_id = exposure.exposure.id`.
- Location detail: `exposure_unit_property.id = exposure_unit.id` (and `unit_type='PROPERTY'`).
- Decode codes via `ref_occupancy.oed_code` / `ref_construction.oed_code` /
  `ref_area (country_code, area_code)`.

## Gotchas
- Always filter `unit_type` before joining a subtype table, or you'll get nulls.
- Money columns are BIGINT — confirm scale; group/sum within a single `currency`.
- `exposure_unit` can be hierarchical (`parent_id`); a unit may be a group node, not a leaf —
  for leaf-level location counts, join to `exposure_unit_property`.
