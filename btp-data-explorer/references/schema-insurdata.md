# `insurdata` (geocoding) — NOT currently reachable

> The insurdata-service stores its data in a **separate PostgreSQL database** (`insurdata`),
> not as a schema inside `<env>_btp_api`. The postgres-mcp server this skill drives connects to
> `<env>_btp_api`, so **`insurdata` data cannot be queried here** — `insurdata.*` queries will
> fail with a "schema not found" / permission error.

If a stakeholder needs geocoding analytics (cache-hit rate, provider mix, address-resolution
quality, coverage by country), that requires standing up a **second postgres-mcp instance**
pointed at the `insurdata` database with its own read-only grants. Tell the user it's out of
scope for the current connection rather than attempting the query.

When/if that second instance exists, the relevant tables are `geocode_job`, `geocode_job_item`,
`geocode_address` (unique-address cache; `resolution_level`, `geocode_provider`), and
`geocode_audit`.
