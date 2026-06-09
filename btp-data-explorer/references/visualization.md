# Visualizing results

When a result is a trend, breakdown, or comparison, a chart communicates it far faster than a
table. Render charts with the bundled script so every visual is consistent and follows
data-viz best practices automatically — don't hand-roll matplotlib for the common cases.

## Render with the bundled script

```bash
uv run scripts/render_chart.py --spec spec.json --out chart.png        # static PNG (default)
uv run scripts/render_chart.py --spec - --out chart.html --format html # interactive Plotly, spec on stdin
```

`uv run` self-provisions matplotlib/plotly from the script's inline metadata into an
**ephemeral, uv-cached** environment — no venv is created in the project or `/tmp`, nothing to
clean up, no `pip install`, no PEP-668 errors. Prefer this path.

**Fallback only if `uv` is absent** — this *does* create a throwaway venv, so remove it after:

```bash
python -m venv /tmp/btp-viz && /tmp/btp-viz/bin/pip install -q matplotlib plotly
/tmp/btp-viz/bin/python scripts/render_chart.py --spec spec.json --out chart.png
rm -rf /tmp/btp-viz   # clean up — the venv is disposable
```

Default to **PNG** for an inline answer; offer **HTML** when the user wants to explore
(hover/zoom/filter) or it's a dashboard-style ask.

**Temp artifacts:** if you write a spec or chart to `/tmp` purely to display it inline (not a
file the user asked you to keep), delete it when done (`rm /tmp/spec_*.json /tmp/chart_*`). Charts
the user wants to keep should go to a path they choose, not `/tmp`.

### Spec shape

```json
{
  "type": "bar",
  "title": "US property TIV by occupancy",
  "subtitle": "dev_btp_api · TIV scale unconfirmed (whole units assumed)",
  "x": "occupancy", "y": "tiv",
  "y_format": "compact", "currency": "USD",
  "sort": "desc", "max_categories": 12,
  "data": [ {"occupancy": "Entertainment", "tiv": 1737821134916}, ... ]
}
```

- `type`: `bar | hbar | grouped_bar | stacked_bar | line | multiline | area | scatter | small_multiples`
- `y`: a field name (or list of fields for multi-measure line). `series`: grouping field for
  `grouped_bar`/`stacked_bar`/`multiline`.
- `y_format`: `number | currency | percent | compact`. `percent` auto-scales 0–1 fractions to %.
- `small_multiples` takes a `panels` array (one `{y, title, y_format}` per metric) — this is how
  you show **two different measures together** (see the dual-axis note below).

## Pick the chart type by the question's intent

| The user wants to show… | Use |
|---|---|
| Compare a value across categories | `bar` (≤ ~12 cats) / `hbar` (more, or long labels) |
| A trend over time | `line` (or `multiline` for a few series) |
| Part-to-whole over time/category | `stacked_bar` |
| Compare sub-groups within categories | `grouped_bar` |
| Two different measures across the same categories | `small_multiples` (NOT dual-axis) |
| Relationship between two numerics | `scatter` |
| Distribution of one numeric | bucket in SQL → `bar` |

## Best practices the script applies (and you should respect)

- **No dual-axis.** Two y-axes on one plot invites false-correlation misreading and the scales
  are arbitrary. Use `small_multiples` (side-by-side panels, shared categories) instead. Only if
  a user explicitly insists on one chart, label both units unmistakably.
- **Colorblind-safe Wong palette** (`#0072B2 #E69F00 #009E73 #CC79A7 #D55E00 …`) — already the
  default `colorway`. Keep color meaning consistent across a set of charts.
- **Direct labeling.** Bars get value labels; lines get an end-of-line series label — easier to
  read than hunting a legend. (Grouped/stacked keep a legend; direct labels would clutter.)
- **Never truncate a value axis** — bars start at 0 (the script does this; don't override).
- **Sort** bars by value (`"sort": "desc"`) unless the category order is meaningful (e.g. time).
- **Cap series/categories** (~7 series, ~12 bars). Use `max_categories` to roll the tail into
  "Other"; for time series with many series, plot the top few + "Other".
- **Format numbers for humans:** `compact` ($1.7B), `currency`, or `percent`. Never dump raw
  BIGINTs in a chart. Carry the same money-scale caveat from the query into the chart `subtitle`.
- **One idea per chart.** If the answer has two stories, make two charts.

## When to hand-roll

For an unusual chart the script doesn't cover (heatmap, funnel, geo map), write custom code, but
`import` the shared style so it still matches:
```python
from render_chart import WONG, format_value
```
Keep the same rules: Wong palette, direct labels, formatted axes, no dual-axis, no truncation.
