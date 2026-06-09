# Metric recipes (the Metabase replacements)

Starting-point SQL for the dashboards stakeholders ask for. **Adapt, don't paste blindly** —
confirm column names with `get_object_details`, confirm money scale, and adjust the time
window. All queries are single read-only `SELECT`s (restricted-mode safe). Add `LIMIT` when
returning rows rather than aggregates.

Conventions used below: `date_trunc('month', created_date)` for monthly buckets; filter
`deleted_date IS NULL` where the column exists; group money by `currency`.

## Portfolio

**Exposures (policies) created per month by line of business**
```sql
SELECT date_trunc('month', e.created_date) AS month,
       s.line_of_business,
       count(*) AS exposures
FROM exposure.exposure e
JOIN exposure.exposure_set s ON s.id = e.exposure_set_id
WHERE e.exposure_type = 'REGISTER'
  AND e.created_date >= now() - interval '12 months'
GROUP BY 1, 2
ORDER BY 1, 2;
```

**Total insured value by line of business and currency**
```sql
SELECT s.line_of_business, e.currency, sum(e.total_insured_value) AS tiv
FROM exposure.exposure e
JOIN exposure.exposure_set s ON s.id = e.exposure_set_id
WHERE e.exposure_type = 'REGISTER'
GROUP BY 1, 2 ORDER BY tiv DESC;
```

**TIV by country (property locations)**
```sql
SELECT p.address_country, p.currency, sum(p.total_insured_value) AS tiv, count(*) AS locations
FROM property.exposure_unit_property p
JOIN property.exposure_unit u ON u.id = p.id AND u.unit_type = 'PROPERTY'
GROUP BY 1, 2 ORDER BY tiv DESC;
```

**Exposure status funnel (current distribution)**
```sql
SELECT status, count(*) FROM exposure.exposure
WHERE exposure_type = 'REGISTER' GROUP BY 1 ORDER BY 2 DESC;
```

**In-force vs expired**
```sql
SELECT CASE WHEN expiration_date >= now() AND inception_date <= now() THEN 'in_force'
            WHEN expiration_date < now() THEN 'expired' ELSE 'future' END AS state,
       count(*)
FROM exposure.exposure WHERE exposure_type = 'REGISTER' GROUP BY 1;
```

## Data quality

**Field-completeness trend (platform-wide, monthly avg)**
```sql
SELECT date_trunc('month', created_date) AS month, avg(field_completeness) AS avg_completeness
FROM exposure.metric_field_completeness
WHERE created_date >= now() - interval '12 months'
GROUP BY 1 ORDER BY 1;
```

**Units by review status and type**
```sql
SELECT unit_type, review_status, count(*) FROM property.exposure_unit
GROUP BY 1, 2 ORDER BY 1, 3 DESC;
```

## Operations / onboarding

**Intake cycle time (median days submitted→validated, by month)**
```sql
SELECT date_trunc('month', submitted_date) AS month,
       percentile_cont(0.5) WITHIN GROUP (
         ORDER BY EXTRACT(epoch FROM (validated_date - submitted_date)) / 86400.0
       ) AS median_days
FROM exposure.intake_request
WHERE submitted_date IS NOT NULL AND validated_date IS NOT NULL
GROUP BY 1 ORDER BY 1;
```

**Intake job failure rate by week**
```sql
SELECT date_trunc('week', created_date) AS week,
       count(*) FILTER (WHERE queued_job_status = 'FAILED')::numeric / nullif(count(*),0) AS fail_rate
FROM exposure.intake_job
WHERE created_date >= now() - interval '8 weeks'
GROUP BY 1 ORDER BY 1;
```

## Engagement (opaque user ids — counts only, no identity)

**Monthly active users & orgs**
```sql
SELECT date_trunc('month', login_timestamp) AS month,
       count(DISTINCT auth0_user_id) AS active_users,
       count(DISTINCT auth0_org_id)  AS active_orgs
FROM iam.login_activity
WHERE login_timestamp >= now() - interval '12 months'
GROUP BY 1 ORDER BY 1;
```

**Most-viewed exposures (last 30 days)**
```sql
SELECT exposure_id, count(*) AS views
FROM iam.exposure_usage_event
WHERE event_type = 'VIEW' AND created_date >= now() - interval '30 days'
GROUP BY 1 ORDER BY views DESC LIMIT 20;
```

**Members per org (active)**
```sql
SELECT o.display_name, count(*) AS members
FROM iam.org_member m JOIN iam.organization o ON o.auth0_org_id = m.auth0_org_id
WHERE m.deleted_at IS NULL
GROUP BY 1 ORDER BY members DESC;
```

## Comms & help center

**Email opt-out rate**
```sql
SELECT count(*) FILTER (WHERE opt_out)::numeric / nullif(count(*),0) AS opt_out_rate,
       avg(invite_accepted::int) AS invite_acceptance_rate
FROM email.notification_eligibility;
```

**Top help-center searches / zero-result searches**
```sql
-- confirm the JSONB key first; 'query' is a guess
SELECT request ->> 'query' AS q, count(*) AS searches, sum((total_hits = 0)::int) AS zero_result
FROM helpcenter.query_history
WHERE created_date >= now() - interval '90 days'
GROUP BY 1 ORDER BY searches DESC LIMIT 25;
```

## Geocoding quality

Not available from this connection — the `insurdata` geocoding data lives in a separate
database. If geocoding analytics are needed, that requires a second MCP instance pointed at the
`insurdata` database. Don't attempt `insurdata.*` queries here; they will fail.
