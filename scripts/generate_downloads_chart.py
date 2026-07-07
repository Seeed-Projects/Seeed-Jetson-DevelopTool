#!/usr/bin/env python3
"""Generate an SVG download trend chart from pypistats.org and save it to assets/.

This script is meant to be run by the update-downloads-chart GitHub Actions
workflow, but can also be executed locally:

    python scripts/generate_downloads_chart.py
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


PROJECT = "seeed-jetson-developer"
API_URL = f"https://pypistats.org/api/packages/{PROJECT}/overall"
OUTPUT = Path(__file__).parent.parent / "assets" / "downloads-chart.svg"

# Chart dimensions
WIDTH = 800
HEIGHT = 320
MARGIN_LEFT = 60
MARGIN_RIGHT = 30
MARGIN_TOP = 40
MARGIN_BOTTOM = 50
PLOT_WIDTH = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
PLOT_HEIGHT = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM

# Colors (light theme, matches the pepy screenshot style)
BG = "#f7f4ed"
GRID = "#e0dcd3"
LINE = "#c17a45"
FILL = "rgba(193, 122, 69, 0.12)"
TEXT = "#5c5a55"
TITLE = "#3b3a36"


def fetch_data(retries: int = 3, delay: float = 2.0) -> dict:
    req = Request(API_URL, headers={"Accept": "application/json", "User-Agent": f"{PROJECT}-chart-generator/1.0"})
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as exc:
            last_err = exc
            if exc.code == 429:
                wait = delay * (2 ** attempt)
                print(f"Rate limited (429), retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Failed to fetch download stats after {retries} attempts: {last_err}")


def aggregate_daily(data: list[dict]) -> dict[str, int]:
    daily: defaultdict[str, int] = defaultdict(int)
    for row in data:
        if row.get("category") != "with_mirrors":
            continue
        daily[row["date"]] += int(row.get("downloads", 0))
    return dict(daily)


def smooth_series(dates: list[str], values: list[int], window: int = 7) -> list[float]:
    if len(values) < window:
        return [float(v) for v in values]
    smoothed: list[float] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        smoothed.append(sum(chunk) / len(chunk))
    return smoothed


def generate_svg(dates: list[str], values: list[int]) -> str:
    if not dates:
        raise RuntimeError("No download data available")

    smoothed = smooth_series(dates, values, window=7)
    max_val = max(smoothed) if max(smoothed) > 0 else 1

    # Nice Y-axis max
    magnitude = 10 ** (len(str(int(max_val))) - 1)
    y_max = ((int(max_val) // magnitude) + 1) * magnitude
    if y_max / magnitude <= 2:
        y_max = ((int(max_val) // (magnitude // 2)) + 1) * (magnitude // 2)

    def x(i: int) -> float:
        return MARGIN_LEFT + (i / (len(dates) - 1)) * PLOT_WIDTH

    def y(v: float) -> float:
        return MARGIN_TOP + PLOT_HEIGHT - (v / y_max) * PLOT_HEIGHT

    # Build line path
    points = [(x(i), y(v)) for i, v in enumerate(smoothed)]
    line_path = f"M {points[0][0]:.1f} {points[0][1]:.1f}"
    for px, py in points[1:]:
        line_path += f" L {px:.1f} {py:.1f}"

    # Build fill area path
    fill_path = line_path + f" L {points[-1][0]:.1f} {MARGIN_TOP + PLOT_HEIGHT:.1f} L {points[0][0]:.1f} {MARGIN_TOP + PLOT_HEIGHT:.1f} Z"

    # Date labels: pick ~6 evenly spaced dates
    label_indices = [int(round(i * (len(dates) - 1) / 5)) for i in range(6)]
    date_labels = []
    for idx in label_indices:
        dt = datetime.strptime(dates[idx], "%Y-%m-%d")
        label = dt.strftime("%b %d")
        date_labels.append((x(idx), MARGIN_TOP + PLOT_HEIGHT + 22, label))

    # Y-axis labels
    y_ticks = 5
    y_labels = []
    for i in range(y_ticks + 1):
        val = (y_max / y_ticks) * i
        yy = MARGIN_TOP + PLOT_HEIGHT - (val / y_max) * PLOT_HEIGHT
        y_labels.append((MARGIN_LEFT - 10, yy, int(val)))

    # Grid lines
    grid_lines = ""
    for _, yy, _ in y_labels[1:]:
        grid_lines += (
            f'<line x1="{MARGIN_LEFT}" y1="{yy:.1f}" x2="{MARGIN_LEFT + PLOT_WIDTH}" y2="{yy:.1f}" '
            f'stroke="{GRID}" stroke-width="1" stroke-dasharray="3,3" />\n'
        )

    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}" style="background-color:{BG}">',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BG}" rx="6"/>',
        f'<text x="{WIDTH / 2}" y="26" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="16" font-weight="600" fill="{TITLE}">PyPI Downloads Trend (90 days)</text>',
        grid_lines,
        f'<path d="{fill_path}" fill="{FILL}" stroke="none"/>',
        f'<path d="{line_path}" fill="none" stroke="{LINE}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>',
    ]

    # Y-axis labels
    for lx, ly, val in y_labels:
        svg_parts.append(
            f'<text x="{lx}" y="{ly + 4}" text-anchor="end" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="11" fill="{TEXT}">{val}</text>'
        )

    # X-axis labels
    for lx, ly, label in date_labels:
        svg_parts.append(
            f'<text x="{lx}" y="{ly}" text-anchor="middle" font-family="system-ui, -apple-system, Segoe UI, sans-serif" font-size="11" fill="{TEXT}">{label}</text>'
        )

    # Axis lines
    svg_parts.append(
        f'<line x1="{MARGIN_LEFT}" y1="{MARGIN_TOP}" x2="{MARGIN_LEFT}" y2="{MARGIN_TOP + PLOT_HEIGHT}" stroke="{GRID}" stroke-width="1"/>'
    )
    svg_parts.append(
        f'<line x1="{MARGIN_LEFT}" y1="{MARGIN_TOP + PLOT_HEIGHT}" x2="{MARGIN_LEFT + PLOT_WIDTH}" y2="{MARGIN_TOP + PLOT_HEIGHT}" stroke="{GRID}" stroke-width="1"/>'
    )

    svg_parts.append("</svg>")
    return "\n".join(svg_parts)


def main() -> None:
    raw = fetch_data()
    daily = aggregate_daily(raw.get("data", []))

    # Fill missing days in the last 90 days
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=89)
    dates = []
    values = []
    current = start
    while current <= end:
        key = current.isoformat()
        dates.append(key)
        values.append(daily.get(key, 0))
        current += timedelta(days=1)

    svg = generate_svg(dates, values)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg, encoding="utf-8")
    print(f"Wrote {OUTPUT} ({len(dates)} days, max daily downloads {max(values)})")


if __name__ == "__main__":
    main()
