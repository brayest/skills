# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib>=3.8", "plotly>=5.20"]
# ///
"""
render_chart.py — house-style chart renderer for btp-data-explorer.

Render a chart from a compact JSON spec, applying data-viz best practices
automatically (colorblind-safe Wong palette, direct value labels, formatted
axes, sorting, no chartjunk, no implicit dual-axis).

Usage (preferred — self-provisions deps, no manual venv):
    uv run scripts/render_chart.py --spec spec.json --out chart.png
    uv run scripts/render_chart.py --spec - --out chart.html --format html   # stdin
The uv path uses an ephemeral, uv-cached env — nothing is written to the project or /tmp,
so there is nothing to clean up. Fallback without uv creates a disposable venv; remove it after:
    python -m venv /tmp/btp-viz && /tmp/btp-viz/bin/pip install matplotlib plotly
    /tmp/btp-viz/bin/python scripts/render_chart.py --spec spec.json --out chart.png
    rm -rf /tmp/btp-viz

Spec (JSON):
{
  "type": "bar|hbar|grouped_bar|stacked_bar|line|multiline|area|scatter|small_multiples",
  "title": "US Property TIV by country",
  "subtitle": "dev_btp_api · TIV scale unconfirmed",   # optional caveat line
  "x": "country",                  # category / x field
  "y": "tiv",                      # measure field (string), or ["a","b"] for multi-measure
  "series": "segment",             # optional grouping field (grouped/stacked/multiline)
  "y_format": "number|currency|percent|compact",
  "currency": "USD",               # symbol hint for currency/compact
  "sort": "desc|asc|none",         # category ordering for bar/hbar
  "max_categories": 12,            # optional: keep top N, group the rest into "Other"
  "data": [ {"country":"GB","tiv":4390130915207}, ... ],
  # small_multiples: one panel per measure (the dual-axis replacement)
  "panels": [ {"y":"tiv","title":"TIV","y_format":"compact"},
              {"y":"completeness","title":"Avg completeness","y_format":"percent"} ]
}
"""
import argparse
import json
import sys

# Wong colorblind-safe palette (Okabe-Ito); distinguishable across common CVD types.
WONG = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442", "#000000"]
_SYMBOL = {"USD": "$", "GBP": "£", "EUR": "€", "JPY": "¥", "CNY": "¥", "INR": "₹"}


def _is_fraction(values):
    nums = [v for v in values if isinstance(v, (int, float))]
    return bool(nums) and max(nums) <= 1.0


def format_value(v, fmt="number", currency="USD", as_fraction=None):
    """Format a single value for a label/tick per the requested format."""
    if v is None:
        return ""
    if fmt == "percent":
        scaled = v * 100 if (as_fraction if as_fraction is not None else v <= 1.0) else v
        return f"{scaled:.0f}%"
    if fmt in ("compact", "currency"):
        sym = _SYMBOL.get(currency, "") if fmt == "currency" or fmt == "compact" else ""
        sym = _SYMBOL.get(currency, "") if fmt == "currency" else (_SYMBOL.get(currency, "") if fmt == "compact" else "")
        n = float(v)
        for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
            if abs(n) >= div:
                return f"{sym}{n / div:.1f}{unit}"
        return f"{sym}{n:,.0f}"
    return f"{v:,.0f}" if isinstance(v, (int, float)) else str(v)


def _prep_rows(spec, y_field):
    rows = [r for r in spec["data"] if r.get(y_field) is not None]
    sort = spec.get("sort", "desc")
    if sort in ("desc", "asc"):
        rows.sort(key=lambda r: r.get(y_field) or 0, reverse=(sort == "desc"))
    maxc = spec.get("max_categories")
    if maxc and len(rows) > maxc:
        keep, rest = rows[:maxc], rows[maxc:]
        other = sum((r.get(y_field) or 0) for r in rest)
        keep.append({spec["x"]: "Other", y_field: other})
        rows = keep
    return rows


# --------------------------------------------------------------------------- #
# matplotlib (PNG)
# --------------------------------------------------------------------------- #
def render_png(spec, out):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False,
                         "font.size": 11, "axes.titlesize": 14})
    t = spec["type"]
    title, subtitle = spec.get("title", ""), spec.get("subtitle")
    cur = spec.get("currency", "USD")

    def finish(fig, ax=None):
        fig.suptitle(title, fontweight="bold", fontsize=14)
        if subtitle and ax is not None:
            ax.set_title(subtitle, fontsize=9, color="#666")
        fig.tight_layout(rect=[0, 0, 1, 0.96])
        fig.savefig(out, dpi=140, bbox_inches="tight")
        print("saved", out)

    if t == "small_multiples":
        panels = spec["panels"]
        x = spec["x"]
        rows = _prep_rows({**spec, "sort": spec.get("sort", "desc")}, panels[0]["y"])
        cats = [r.get(x) for r in rows]
        fig, axes = plt.subplots(1, len(panels), figsize=(6.2 * len(panels), 5.6))
        if len(panels) == 1:
            axes = [axes]
        for i, (ax, p) in enumerate(zip(axes, panels)):
            fmt = p.get("y_format", "number")
            vals = [r.get(p["y"]) for r in rows]
            frac = _is_fraction(vals) if fmt == "percent" else None
            ax.bar(range(len(cats)), [v or 0 for v in vals], color=WONG[i % len(WONG)])
            ax.set_title(p.get("title", p["y"]), fontsize=11, color=WONG[i % len(WONG)], fontweight="bold")
            ax.set_xticks(range(len(cats)))
            ax.set_xticklabels(cats, rotation=30, ha="right")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(
                lambda v, _p, f=fmt, fr=frac: format_value(v, f, cur, fr)))
            ax.grid(axis="y", linestyle=":", alpha=0.4)
            for xi, v in enumerate(vals):
                ax.text(xi, (v or 0), format_value(v, fmt, cur, frac), ha="center",
                        va="bottom", fontsize=7.5, color="#333")
        finish(fig)
        return

    fig, ax = plt.subplots(figsize=(12, 6.5))
    fmt = spec.get("y_format", "number")

    if t in ("bar", "hbar"):
        y = spec["y"]
        rows = _prep_rows(spec, y)
        cats = [r.get(spec["x"]) for r in rows]
        vals = [r.get(y) or 0 for r in rows]
        frac = _is_fraction(vals) if fmt == "percent" else None
        if t == "bar":
            ax.bar(range(len(cats)), vals, color=WONG[0])
            ax.set_xticks(range(len(cats)))
            ax.set_xticklabels(cats, rotation=30, ha="right")
            ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: format_value(v, fmt, cur, frac)))
            for xi, v in enumerate(vals):
                ax.text(xi, v, format_value(v, fmt, cur, frac), ha="center", va="bottom", fontsize=8)
        else:
            cats, vals = cats[::-1], vals[::-1]
            ax.barh(range(len(cats)), vals, color=WONG[0])
            ax.set_yticks(range(len(cats)))
            ax.set_yticklabels(cats)
            ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: format_value(v, fmt, cur, frac)))
            for yi, v in enumerate(vals):
                ax.text(v, yi, " " + format_value(v, fmt, cur, frac), va="center", fontsize=8)
        ax.grid(axis=("y" if t == "bar" else "x"), linestyle=":", alpha=0.4)

    elif t in ("line", "multiline", "area"):
        x = spec["x"]
        ys = spec["y"] if isinstance(spec["y"], list) else [spec["y"]]
        series_field = spec.get("series")
        xs = sorted({r.get(x) for r in spec["data"]}, key=lambda v: (v is None, v))
        if series_field:
            groups = {}
            for r in spec["data"]:
                groups.setdefault(r.get(series_field), {})[r.get(x)] = r.get(ys[0])
            lines = list(groups.items())
        else:
            lines = [(yf, {r.get(x): r.get(yf) for r in spec["data"]}) for yf in ys]
        frac = _is_fraction([v for _, d in lines for v in d.values()]) if fmt == "percent" else None
        for i, (name, dmap) in enumerate(lines):
            yv = [dmap.get(xx) for xx in xs]
            color = WONG[i % len(WONG)]
            if t == "area":
                ax.fill_between(range(len(xs)), [v or 0 for v in yv], color=color, alpha=0.30)
            ax.plot(range(len(xs)), yv, marker="o", color=color, linewidth=2.2, label=str(name))
            # direct end-of-line label
            last = next((j for j in range(len(xs) - 1, -1, -1) if yv[j] is not None), None)
            if last is not None:
                ax.text(last, yv[last], "  " + str(name), color=color, fontsize=9, va="center")
        ax.set_xticks(range(len(xs)))
        ax.set_xticklabels(xs, rotation=30, ha="right")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: format_value(v, fmt, cur, frac)))
        ax.grid(axis="y", linestyle=":", alpha=0.4)

    elif t in ("grouped_bar", "stacked_bar"):
        x, series_field = spec["x"], spec["series"]
        ys = spec["y"] if isinstance(spec["y"], list) else [spec["y"]]
        cats = sorted({r.get(x) for r in spec["data"]}, key=lambda v: (v is None, v))
        segs = sorted({r.get(series_field) for r in spec["data"]}, key=lambda v: (v is None, v))
        lookup = {(r.get(x), r.get(series_field)): r.get(ys[0]) for r in spec["data"]}
        import numpy as np
        idx = np.arange(len(cats))
        if t == "grouped_bar":
            w = 0.8 / max(len(segs), 1)
            for i, s in enumerate(segs):
                ax.bar(idx + i * w, [lookup.get((c, s)) or 0 for c in cats], width=w,
                       color=WONG[i % len(WONG)], label=str(s))
            ax.set_xticks(idx + 0.4 - w / 2)
        else:
            bottom = np.zeros(len(cats))
            for i, s in enumerate(segs):
                vals = np.array([lookup.get((c, s)) or 0 for c in cats], dtype=float)
                ax.bar(idx, vals, bottom=bottom, color=WONG[i % len(WONG)], label=str(s))
                bottom += vals
            ax.set_xticks(idx)
        ax.set_xticklabels(cats, rotation=30, ha="right")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: format_value(v, fmt, cur)))
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle=":", alpha=0.4)

    elif t == "scatter":
        xf, yf = spec["x"], (spec["y"] if isinstance(spec["y"], str) else spec["y"][0])
        ax.scatter([r.get(xf) for r in spec["data"]], [r.get(yf) for r in spec["data"]],
                   color=WONG[0], alpha=0.6, edgecolor="white", linewidth=0.4)
        ax.set_xlabel(xf)
        ax.set_ylabel(yf)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _p: format_value(v, fmt, cur)))
        ax.grid(linestyle=":", alpha=0.4)
    else:
        sys.exit(f"unknown chart type: {t}")

    finish(fig, ax)


# --------------------------------------------------------------------------- #
# plotly (interactive HTML)
# --------------------------------------------------------------------------- #
def render_html(spec, out):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    t = spec["type"]
    cur = spec.get("currency", "USD")
    fmt = spec.get("y_format", "number")
    title = spec.get("title", "")
    if spec.get("subtitle"):
        title += f"<br><sup>{spec['subtitle']}</sup>"

    def fig_done(fig):
        fig.update_layout(title=title, template="plotly_white", colorway=WONG,
                          font=dict(size=13), margin=dict(t=90))
        fig.write_html(out, include_plotlyjs="cdn")
        print("saved", out)

    if t == "small_multiples":
        x = spec["x"]
        panels = spec["panels"]
        rows = _prep_rows({**spec}, panels[0]["y"])
        cats = [r.get(x) for r in rows]
        fig = make_subplots(rows=1, cols=len(panels), subplot_titles=[p.get("title", p["y"]) for p in panels])
        for i, p in enumerate(panels):
            fig.add_trace(go.Bar(x=cats, y=[r.get(p["y"]) for r in rows],
                                 marker_color=WONG[i % len(WONG)], name=p.get("title", p["y"])), row=1, col=i + 1)
        fig.update_layout(showlegend=False)
        fig_done(fig)
        return

    fig = go.Figure()
    if t in ("bar", "hbar"):
        y = spec["y"]
        rows = _prep_rows(spec, y)
        cats = [r.get(spec["x"]) for r in rows]
        vals = [r.get(y) or 0 for r in rows]
        text = [format_value(v, fmt, cur) for v in vals]
        if t == "bar":
            fig.add_trace(go.Bar(x=cats, y=vals, marker_color=WONG[0], text=text, textposition="outside"))
        else:
            fig.add_trace(go.Bar(y=cats[::-1], x=vals[::-1], orientation="h", marker_color=WONG[0],
                                 text=text[::-1], textposition="outside"))
    elif t in ("line", "multiline", "area"):
        x = spec["x"]
        ys = spec["y"] if isinstance(spec["y"], list) else [spec["y"]]
        series_field = spec.get("series")
        xs = sorted({r.get(x) for r in spec["data"]}, key=lambda v: (v is None, v))
        if series_field:
            groups = {}
            for r in spec["data"]:
                groups.setdefault(r.get(series_field), {})[r.get(x)] = r.get(ys[0])
            lines = list(groups.items())
        else:
            lines = [(yf, {r.get(x): r.get(yf) for r in spec["data"]}) for yf in ys]
        for name, dmap in lines:
            fig.add_trace(go.Scatter(x=xs, y=[dmap.get(xx) for xx in xs], mode="lines+markers",
                                     name=str(name), fill=("tozeroy" if t == "area" else None)))
    elif t in ("grouped_bar", "stacked_bar"):
        x, series_field = spec["x"], spec["series"]
        ys = spec["y"] if isinstance(spec["y"], list) else [spec["y"]]
        cats = sorted({r.get(x) for r in spec["data"]}, key=lambda v: (v is None, v))
        segs = sorted({r.get(series_field) for r in spec["data"]}, key=lambda v: (v is None, v))
        lookup = {(r.get(x), r.get(series_field)): r.get(ys[0]) for r in spec["data"]}
        for s in segs:
            fig.add_trace(go.Bar(x=cats, y=[lookup.get((c, s)) for c in cats], name=str(s)))
        fig.update_layout(barmode=("stack" if t == "stacked_bar" else "group"))
    elif t == "scatter":
        xf, yf = spec["x"], (spec["y"] if isinstance(spec["y"], str) else spec["y"][0])
        fig.add_trace(go.Scatter(x=[r.get(xf) for r in spec["data"]],
                                 y=[r.get(yf) for r in spec["data"]], mode="markers",
                                 marker=dict(color=WONG[0], opacity=0.65)))
    else:
        sys.exit(f"unknown chart type: {t}")
    fig_done(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True, help="path to JSON spec, or '-' for stdin")
    ap.add_argument("--out", required=True, help="output path (.png or .html)")
    ap.add_argument("--format", choices=["png", "html"], help="override; else inferred from --out")
    a = ap.parse_args()

    raw = sys.stdin.read() if a.spec == "-" else open(a.spec).read()
    spec = json.loads(raw)
    fmt = a.format or ("html" if a.out.lower().endswith(".html") else "png")
    (render_html if fmt == "html" else render_png)(spec, a.out)


if __name__ == "__main__":
    main()
